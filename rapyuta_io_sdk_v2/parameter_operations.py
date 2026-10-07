"""Synchronous and asynchronous filesystem workflows for Parameter trees."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import mimetypes
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Iterable
from pathlib import Path
from pathlib import PureWindowsPath
from typing import Any
from urllib.parse import quote

import httpx

from rapyuta_io_sdk_v2.context import RequestContext
from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError, SDKError
from rapyuta_io_sdk_v2.features import require_dependency
from rapyuta_io_sdk_v2.models.parameter import ParameterBlobList, ParameterNode
from rapyuta_io_sdk_v2.utils import handle_server_errors


_TREE = "/api/paramserver/tree"
_TREE_BLOBS = "/api/paramserver/treeblobs"
_BINARY_FILE = "/api/paramserver/binaryfilenode"
_MAX_INLINE_PAYLOAD = 128 * 1024
_YAML_TYPES = {".yaml", ".yml"}
_IO_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rio-parameter-io")


class ParameterPathError(ValueError):
    """The Parameter service returned a path that cannot be safely used."""

    def __init__(self, message: str, tree_path: str | None = None):
        self.tree_path = tree_path
        super().__init__(message)


def _with_tree_path(exc: Exception, tree_path: str | None) -> Exception:
    try:
        if getattr(exc, "tree_path", None) is None:
            exc.tree_path = tree_path  # type: ignore[attr-defined]
    except Exception:
        wrapped = SDKError(str(exc))
        wrapped.tree_path = tree_path  # type: ignore[attr-defined]
        return wrapped
    return exc


async def _run_blocking(function, *args):
    """Run filesystem work off-loop and wait for an in-flight call on cancellation."""
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_IO_EXECUTOR, function, *args)
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        # The operation may be writing a temporary file. Wait until the current
        # small operation is finished so its caller can reliably clean that file.
        try:
            await asyncio.shield(future)
        except Exception:
            pass
        raise


async def _run_blocking_with_result_cleanup(function, cleanup, *args):
    """Dispose of a worker result if cancellation arrives before it is returned."""
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_IO_EXECUTOR, function, *args)
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        try:
            result = await asyncio.shield(future)
            cleanup_future = loop.run_in_executor(_IO_EXECUTOR, cleanup, result)
            await asyncio.shield(cleanup_future)
        except Exception:
            pass
        raise


def _api_path(path: str) -> str:
    """Quote each path segment while retaining the service's slash hierarchy."""
    return "/".join(quote(part, safe="") for part in path.split("/"))


def _response_data(response: httpx.Response, *, require_envelope: bool = True) -> Any:
    handle_server_errors(response)
    try:
        body = response.json()
    except (ValueError, UnicodeDecodeError) as exc:
        if not require_envelope and not response.content:
            return None
        raise SDKError("Parameter API returned invalid JSON", response=response) from exc
    if not require_envelope:
        if isinstance(body, dict) and (
            body.get("success") is False or str(body.get("status", "")).lower() == "error"
        ):
            message = (
                body.get("error")
                or body.get("message")
                or "Parameter API operation failed"
            )
            raise SDKError(str(message), response=response, details=body)
        return body.get("data") if isinstance(body, dict) and "data" in body else body
    if not isinstance(body, dict) or "data" not in body:
        raise SDKError(
            "Parameter API response is missing its data envelope", response=response
        )
    return body["data"]


def _safe_name(name: Any, parent: str) -> str:
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or Path(name).is_absolute()
        or bool(PureWindowsPath(name).drive)
        or "\x00" in name
    ):
        raise ParameterPathError(f"Unsafe Parameter node name: {name!r}", parent)
    return name


def _destination(root: Path, parts: Iterable[str], tree_path: str | None = None) -> Path:
    target = root
    for part in parts:
        target = target / _safe_name(part, tree_path or "")
    root_resolved = root.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ParameterPathError(
            "Parameter path escapes the destination", tree_path
        ) from exc
    if target == root:
        raise ParameterPathError(
            "Parameter path must be below the destination root", tree_path
        )
    # Walk without following any pre-existing symlink, including the final file.
    cursor = root
    for part in target.relative_to(root).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ParameterPathError("Refusing to write through a symlink", tree_path)
    try:
        target.resolve(strict=False).relative_to(root_resolved)
    except ValueError as exc:
        raise ParameterPathError(
            "Parameter path escapes the destination", tree_path
        ) from exc
    return target


def _ensure_directory(path: Path, root: Path, tree_path: str | None = None) -> None:
    if path.exists() and (path.is_symlink() or not path.is_dir()):
        raise ParameterPathError("Destination path is not a safe directory", tree_path)
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ParameterPathError("Destination directory escapes root", tree_path) from exc


def _load_yaml(text: str, file_path: Path) -> None:
    yaml = require_dependency("yaml", "parameters")
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML file: {file_path}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"Parameter YAML must contain a mapping: {file_path}")


def _inline_payload(data: str, content_type: str) -> dict[str, Any]:
    return {"type": "FileNode", "data": data, "contentType": content_type}


def _uses_binary(file_path: Path, data: str | None, content_type: str | None) -> bool:
    if data is None:
        return True
    payload_size = (
        len(
            json.dumps(
                _inline_payload(data, content_type or "text/yaml"),
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        + 200
    )
    return payload_size > _MAX_INLINE_PAYLOAD


def _tree_root_entries(root: Path, tree_names: list[str] | None) -> list[Path]:
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Parameter root directory does not exist: {root}")
    selected = set(tree_names or [])
    entries = []
    for child in root.iterdir():
        if selected and child.name not in selected:
            continue
        if child.is_symlink():
            raise ParameterPathError("Refusing to upload a symlink", child.name)
        if child.is_dir():
            _safe_name(child.name, "")
            entries.append(child)
    return entries


def _plan_tree_upload(
    root: Path, tree: Path, as_folder: bool
) -> list[tuple[str, dict[str, Any] | Path]]:
    """Read/validate the tree and produce ordered node and file operations."""
    ops: list[tuple[str, dict[str, Any] | Path]] = [(tree.name, {"type": "ValueNode"})]

    def visit(directory: Path, rel: Path, level: int) -> None:
        legacy_attribute_parent = level % 2 == 0
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            _safe_name(child.name, rel.as_posix())
            if child.is_symlink():
                raise ParameterPathError(
                    "Refusing to upload a symlink", (rel / child.name).as_posix()
                )
            child_rel = rel / child.name
            api_rel = child_rel.as_posix()
            if child.is_dir():
                node_type = (
                    "FolderNode"
                    if as_folder
                    else ("ValueNode" if legacy_attribute_parent else "AttributeNode")
                )
                ops.append((api_rel, {"type": node_type}))
                visit(child, child_rel, level + 1)
                continue
            if not child.is_file():
                continue
            if not as_folder and legacy_attribute_parent:
                # v1's parameter tree convention stores files only below attribute nodes.
                continue
            try:
                suffix = child.suffix.lower()
                content_type = "application/json" if suffix == ".json" else "text/yaml"
                text_data: str | None = None
                if suffix == ".json" or suffix in _YAML_TYPES:
                    text_data = child.read_text(encoding="utf-8")
                    if suffix == ".json":
                        try:
                            json.loads(text_data)
                        except json.JSONDecodeError as exc:
                            raise ValueError(f"Invalid JSON file: {child}") from exc
                    else:
                        _load_yaml(text_data, child)
                if text_data is not None and not _uses_binary(
                    child, text_data, content_type
                ):
                    ops.append((api_rel, _inline_payload(text_data, content_type)))
                else:
                    ops.append((api_rel, child))
            except Exception as exc:
                raise _with_tree_path(exc, api_rel)

    visit(tree, Path(tree.name), 1)
    return ops


def _validate_args(
    rootdir: str | Path,
    tree_names: list[str] | None,
    delete: bool,
    as_folder: bool | None = None,
) -> Path:
    if not isinstance(rootdir, (str, Path)):
        raise TypeError("rootdir must be a string or pathlib.Path")
    if tree_names is not None and (
        not isinstance(tree_names, list)
        or any(not isinstance(name, str) for name in tree_names)
    ):
        raise TypeError("tree_names must be a list of strings or None")
    if not isinstance(delete, bool):
        raise TypeError("delete_existing_trees must be a boolean")
    if as_folder is not None and not isinstance(as_folder, bool):
        raise TypeError("as_folder must be a boolean")
    return Path(rootdir).expanduser().absolute()


def _headers(client: Any, context: RequestContext | None, **extra: str) -> dict[str, str]:
    headers = client.config.get_headers(context=context)
    headers.update(extra)
    return headers


def _signed_request(
    client: Any,
    method: str,
    url: str,
    *,
    content: Any = None,
    headers: dict[str, str] | None = None,
    stream: bool = False,
) -> httpx.Response:
    # send(Request) bypasses Client.build_request, so externally supplied default
    # headers and cookies cannot leak platform credentials to the signed host.
    request = httpx.Request(method, url, headers=headers, content=content)
    return client.c.send(request, auth=None, follow_redirects=False, stream=stream)


async def _async_signed_request(
    client: Any,
    method: str,
    url: str,
    *,
    content: Any = None,
    headers: dict[str, str] | None = None,
    stream: bool = False,
) -> httpx.Response:
    request = httpx.Request(method, url, headers=headers, content=content)
    return await client.c.send(request, auth=None, follow_redirects=False, stream=stream)


def _mime(file_path: Path) -> tuple[str, str | None]:
    guessed, encoding = mimetypes.guess_type(file_path.name)
    content_type = guessed or "application/octet-stream"
    if file_path.suffix.lower() in _YAML_TYPES or content_type in {
        "application/json",
        "application/yaml",
        "text/yaml",
        "application/x-yaml",
    }:
        content_type = "application/octet-stream"
    return content_type, encoding


def _check_signed_transfer(response: httpx.Response) -> None:
    handle_server_errors(response)
    if not 200 <= response.status_code < 300:
        raise SDKError(
            f"Signed blob transfer failed with HTTP {response.status_code}",
            status_code=response.status_code,
            response=response,
        )


def _upload_binary(
    client: Any, tree_path: str, file_path: Path, context: RequestContext | None
) -> None:
    content = file_path.read_bytes()
    checksum = hashlib.md5(content).hexdigest()
    content_type, encoding = _mime(file_path)
    headers = _headers(
        client,
        context,
        **{
            "X-Rapyuta-Params-Version": "0",
            "Content-Type": content_type,
            "Checksum": checksum,
        },
    )
    if encoding:
        headers["Content-Encoding"] = encoding
    response = client.c.put(
        f"{client.core_api_host}{_BINARY_FILE}/{_api_path(tree_path)}", headers=headers
    )
    data = _response_data(response)
    if not isinstance(data, dict):
        raise SDKError(
            "Binary Parameter response data must be an object", response=response
        )
    blob_ref_id, signed_url = data.get("blobRefId"), data.get("uploadUrl")
    if not blob_ref_id or not signed_url:
        return
    signed_headers = {
        "x-ms-blob-type": "BlockBlob",
        "x-ms-blob-content-type": content_type,
        "x-ms-blob-content-md5": base64.b64encode(hashlib.md5(content).digest()).decode(
            "ascii"
        ),
        "Content-Length": str(len(content)),
    }
    if encoding:
        signed_headers["x-ms-blob-content-encoding"] = encoding
    upload = _signed_request(
        client, "PUT", signed_url, content=content, headers=signed_headers
    )
    _check_signed_transfer(upload)
    tree_name = tree_path.split("/", 1)[0]
    commit = client.c.patch(
        f"{client.core_api_host}{_BINARY_FILE}/{_api_path(tree_name)}/blobref/{quote(str(blob_ref_id), safe='')}",
        headers=headers,
    )
    try:
        _response_data(commit, require_envelope=False)
    except Exception as exc:
        message = str(exc).lower()
        if (
            "blobref already uploaded" not in message
            and "signed url not generated" not in message
        ):
            raise


async def _async_upload_binary(
    client: Any, tree_path: str, file_path: Path, context: RequestContext | None
) -> None:
    content = await _run_blocking(file_path.read_bytes)
    checksum = hashlib.md5(content).hexdigest()
    content_type, encoding = _mime(file_path)
    headers = _headers(
        client,
        context,
        **{
            "X-Rapyuta-Params-Version": "0",
            "Content-Type": content_type,
            "Checksum": checksum,
        },
    )
    if encoding:
        headers["Content-Encoding"] = encoding
    response = await client.c.put(
        f"{client.core_api_host}{_BINARY_FILE}/{_api_path(tree_path)}", headers=headers
    )
    data = _response_data(response)
    if not isinstance(data, dict):
        raise SDKError(
            "Binary Parameter response data must be an object", response=response
        )
    blob_ref_id, signed_url = data.get("blobRefId"), data.get("uploadUrl")
    if not blob_ref_id or not signed_url:
        return
    signed_headers = {
        "x-ms-blob-type": "BlockBlob",
        "x-ms-blob-content-type": content_type,
        "x-ms-blob-content-md5": base64.b64encode(hashlib.md5(content).digest()).decode(
            "ascii"
        ),
        "Content-Length": str(len(content)),
    }
    if encoding:
        signed_headers["x-ms-blob-content-encoding"] = encoding
    upload = await _async_signed_request(
        client, "PUT", signed_url, content=content, headers=signed_headers
    )
    _check_signed_transfer(upload)
    tree_name = tree_path.split("/", 1)[0]
    commit = await client.c.patch(
        f"{client.core_api_host}{_BINARY_FILE}/{_api_path(tree_name)}/blobref/{quote(str(blob_ref_id), safe='')}",
        headers=headers,
    )
    try:
        _response_data(commit, require_envelope=False)
    except Exception as exc:
        message = str(exc).lower()
        if (
            "blobref already uploaded" not in message
            and "signed url not generated" not in message
        ):
            raise


def _upload_tree(
    client: Any,
    root: Path,
    tree: Path,
    delete: bool,
    as_folder: bool,
    context: RequestContext | None,
) -> None:
    ops = _plan_tree_upload(root, tree, as_folder)
    tree_name = tree.name
    try:
        if delete:
            response = client.c.delete(
                f"{client.core_api_host}{_TREE}/{_api_path(tree_name)}",
                headers=_headers(client, context),
            )
            _response_data(response, require_envelope=False)
        for tree_path, body in ops:
            try:
                url = f"{client.core_api_host}{_TREE}/{_api_path(tree_path)}"
                if isinstance(body, Path):
                    _upload_binary(client, tree_path, body, context)
                else:
                    response = client.c.put(
                        url, headers=_headers(client, context), json=body
                    )
                    _response_data(response, require_envelope=False)
            except Exception as exc:
                raise _with_tree_path(exc, tree_path)
    except Exception as exc:
        raise _with_tree_path(exc, tree_name)


async def _async_upload_tree(
    client: Any,
    root: Path,
    tree: Path,
    delete: bool,
    as_folder: bool,
    context: RequestContext | None,
) -> None:
    ops = await _run_blocking(_plan_tree_upload, root, tree, as_folder)
    tree_name = tree.name
    try:
        if delete:
            response = await client.c.delete(
                f"{client.core_api_host}{_TREE}/{_api_path(tree_name)}",
                headers=_headers(client, context),
            )
            _response_data(response, require_envelope=False)
        for tree_path, body in ops:
            try:
                url = f"{client.core_api_host}{_TREE}/{_api_path(tree_path)}"
                if isinstance(body, Path):
                    await _async_upload_binary(client, tree_path, body, context)
                else:
                    response = await client.c.put(
                        url, headers=_headers(client, context), json=body
                    )
                    _response_data(response, require_envelope=False)
            except Exception as exc:
                raise _with_tree_path(exc, tree_path)
    except Exception as exc:
        raise _with_tree_path(exc, tree_name)


def _list_trees(client: Any, context: RequestContext | None) -> list[str]:
    response = client.c.get(
        f"{client.core_api_host}{_TREE}", headers=_headers(client, context)
    )
    data = _response_data(response)
    if not isinstance(data, list) or any(not isinstance(name, str) for name in data):
        raise SDKError("Parameter tree list must be an array of names", response=response)
    return data


async def _async_list_trees(client: Any, context: RequestContext | None) -> list[str]:
    response = await client.c.get(
        f"{client.core_api_host}{_TREE}", headers=_headers(client, context)
    )
    data = _response_data(response)
    if not isinstance(data, list) or any(not isinstance(name, str) for name in data):
        raise SDKError("Parameter tree list must be an array of names", response=response)
    return data


def _blob_urls(
    client: Any, tree_names: list[str], context: RequestContext | None
) -> dict[str, str]:
    response = client.c.get(
        f"{client.core_api_host}{_TREE_BLOBS}",
        params={"treeNames": tree_names},
        headers=_headers(client, context),
    )
    data = _response_data(response)
    try:
        blobs = ParameterBlobList.model_validate(data).blob_refs
        return {str(blob.id): blob.signed_url for blob in blobs if blob.signed_url}
    except Exception as exc:
        raise SDKError(
            "Parameter blob list has an invalid shape", response=response
        ) from exc


async def _async_blob_urls(
    client: Any, tree_names: list[str], context: RequestContext | None
) -> dict[str, str]:
    response = await client.c.get(
        f"{client.core_api_host}{_TREE_BLOBS}",
        params={"treeNames": tree_names},
        headers=_headers(client, context),
    )
    data = _response_data(response)
    try:
        blobs = ParameterBlobList.model_validate(data).blob_refs
        return {str(blob.id): blob.signed_url for blob in blobs if blob.signed_url}
    except Exception as exc:
        raise SDKError(
            "Parameter blob list has an invalid shape", response=response
        ) from exc


def _write_node(
    root: Path,
    node: ParameterNode,
    parent_parts: tuple[str, ...],
    blobs: dict[str, str],
    client: Any,
) -> None:
    name = _safe_name(node.name, "/".join(parent_parts))
    parts = parent_parts + (name,)
    path = _destination(root, parts, "/".join(parts))
    if node.type == "FileNode":
        _ensure_directory(path.parent, root, "/".join(parts))
        if node.blob_ref_id:
            url = blobs.get(node.blob_ref_id)
            if not url:
                raise HttpNotFoundError(
                    f"Missing signed URL for Parameter blob {node.blob_ref_id}"
                )
            response = _signed_request(client, "GET", url, stream=True)
            try:
                if response.status_code >= 400:
                    response.read()
                _check_signed_transfer(response)
                _atomic_write(path, response.iter_bytes())
            finally:
                response.close()
        else:
            data = node.data if isinstance(node.data, str) else ""
            _atomic_write(path, (data.encode("utf-8"),))
        return
    _ensure_directory(path, root, "/".join(parts))
    for child in node.children:
        _write_node(root, child, parts, blobs, client)


def _atomic_write(path: Path, chunks: Iterable[bytes]) -> None:
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "wb") as target:
            for chunk in chunks:
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _create_temp_file(directory: Path, filename: str) -> str:
    fd, temp_name = tempfile.mkstemp(prefix=f".{filename}.", suffix=".tmp", dir=directory)
    os.close(fd)
    return temp_name


def _append_temp_file(temp_name: str, chunk: bytes) -> None:
    with open(temp_name, "ab") as target:
        target.write(chunk)


def _sync_temp_file(temp_name: str) -> None:
    with open(temp_name, "ab") as target:
        target.flush()
        os.fsync(target.fileno())


def _remove_temp_file(temp_name: str) -> None:
    try:
        os.unlink(temp_name)
    except FileNotFoundError:
        pass


async def _async_atomic_write(path: Path, chunks: Iterable[bytes]) -> None:
    """Write a temp beside the destination; cancellation removes the temp."""
    temp_name = await _run_blocking_with_result_cleanup(
        _create_temp_file, _remove_temp_file, path.parent, path.name
    )
    try:
        for chunk in chunks:
            await _run_blocking(_append_temp_file, temp_name, chunk)
        await _run_blocking(_sync_temp_file, temp_name)
        # No await after this point: cancellation cannot interrupt the atomic replace.
        os.replace(temp_name, path)
    except BaseException:
        await _run_blocking(_remove_temp_file, temp_name)
        raise


async def _async_write_node(
    root: Path,
    node: ParameterNode,
    parent_parts: tuple[str, ...],
    blobs: dict[str, str],
    client: Any,
) -> None:
    name = _safe_name(node.name, "/".join(parent_parts))
    parts = parent_parts + (name,)
    path = _destination(root, parts, "/".join(parts))
    if node.type == "FileNode":
        await _run_blocking(_ensure_directory, path.parent, root, "/".join(parts))
        if node.blob_ref_id:
            url = blobs.get(node.blob_ref_id)
            if not url:
                raise HttpNotFoundError(
                    f"Missing signed URL for Parameter blob {node.blob_ref_id}"
                )
            response = await _async_signed_request(client, "GET", url, stream=True)
            try:
                if response.status_code >= 400:
                    await response.aread()
                _check_signed_transfer(response)
                temp_name = await _run_blocking_with_result_cleanup(
                    _create_temp_file, _remove_temp_file, path.parent, path.name
                )
                try:
                    async for chunk in response.aiter_bytes():
                        await _run_blocking(_append_temp_file, temp_name, chunk)
                    await _run_blocking(_sync_temp_file, temp_name)
                    # No await after this point: cancellation cannot interrupt replace.
                    os.replace(temp_name, path)
                except BaseException:
                    await _run_blocking(_remove_temp_file, temp_name)
                    raise
            finally:
                await response.aclose()
        else:
            data = node.data if isinstance(node.data, str) else ""
            await _async_atomic_write(path, (data.encode("utf-8"),))
        return
    await _run_blocking(_ensure_directory, path, root, "/".join(parts))
    for child in node.children:
        await _async_write_node(root, child, parts, blobs, client)


def _download_tree(
    client: Any,
    tree_name: str,
    root: Path,
    delete: bool,
    blobs: dict[str, str],
    context: RequestContext | None,
) -> None:
    tree_path = _safe_name(tree_name, "")
    destination = _destination(root, (tree_path,), tree_name)
    try:
        response = client.c.get(
            f"{client.core_api_host}{_TREE}/{_api_path(tree_path)}",
            headers=_headers(client, context),
        )
        data = _response_data(response)
        node = ParameterNode.model_validate(data)
        if node.name != tree_name:
            raise ParameterPathError(
                "Parameter tree response name does not match the requested tree",
                tree_name,
            )
        if delete and destination.exists():
            if destination.is_symlink():
                raise ParameterPathError("Refusing to delete a symlink", tree_name)
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        _write_node(root, node, (), blobs, client)
    except Exception as exc:
        raise _with_tree_path(exc, tree_name)


async def _async_download_tree(
    client: Any,
    tree_name: str,
    root: Path,
    delete: bool,
    blobs: dict[str, str],
    context: RequestContext | None,
) -> None:
    tree_path = _safe_name(tree_name, "")
    destination = _destination(root, (tree_path,), tree_name)
    try:
        response = await client.c.get(
            f"{client.core_api_host}{_TREE}/{_api_path(tree_path)}",
            headers=_headers(client, context),
        )
        data = _response_data(response)
        node = ParameterNode.model_validate(data)
        if node.name != tree_name:
            raise ParameterPathError(
                "Parameter tree response name does not match the requested tree",
                tree_name,
            )
        if delete and destination.exists():
            if destination.is_symlink():
                raise ParameterPathError("Refusing to delete a symlink", tree_name)
            if destination.is_dir():
                await _run_blocking(shutil.rmtree, destination)
            else:
                await _run_blocking(destination.unlink)
        await _async_write_node(root, node, (), blobs, client)
    except Exception as exc:
        raise _with_tree_path(exc, tree_name)


def upload_configurations(
    client: Any,
    rootdir: str | Path,
    tree_names: list[str] | None = None,
    delete_existing_trees: bool = False,
    as_folder: bool = True,
    *,
    context: RequestContext | None = None,
) -> None:
    """Upload local Parameter trees with the supplied SDK client."""
    root = _validate_args(rootdir, tree_names, delete_existing_trees, as_folder)
    for tree in _tree_root_entries(root, tree_names):
        _upload_tree(client, root, tree, delete_existing_trees, as_folder, context)


def download_configurations(
    client: Any,
    rootdir: str | Path,
    tree_names: list[str] | None = None,
    delete_existing_trees: bool = False,
    *,
    context: RequestContext | None = None,
) -> None:
    """Download Parameter trees to the local filesystem."""
    root = _validate_args(rootdir, tree_names, delete_existing_trees)
    _ensure_directory(root, root)
    try:
        api_tree_names = _list_trees(client, context)
    except Exception as exc:
        raise _with_tree_path(exc, "")
    if tree_names:
        api_tree_names = [name for name in api_tree_names if name in tree_names]
    if not api_tree_names:
        raise HttpNotFoundError("One or more Parameter trees not found")
    for name in api_tree_names:
        _safe_name(name, "")
    blobs = _blob_urls(client, api_tree_names, context)
    for name in api_tree_names:
        _download_tree(client, name, root, delete_existing_trees, blobs, context)


async def async_upload_configurations(
    client: Any,
    rootdir: str | Path,
    tree_names: list[str] | None = None,
    delete_existing_trees: bool = False,
    as_folder: bool = True,
    *,
    context: RequestContext | None = None,
) -> None:
    """Upload local Parameter trees with the supplied async SDK client."""
    root = _validate_args(rootdir, tree_names, delete_existing_trees, as_folder)
    trees = await _run_blocking(_tree_root_entries, root, tree_names)
    for tree in trees:
        await _async_upload_tree(
            client, root, tree, delete_existing_trees, as_folder, context
        )


async def async_download_configurations(
    client: Any,
    rootdir: str | Path,
    tree_names: list[str] | None = None,
    delete_existing_trees: bool = False,
    *,
    context: RequestContext | None = None,
) -> None:
    """Download Parameter trees with the supplied async SDK client."""
    root = _validate_args(rootdir, tree_names, delete_existing_trees)
    await _run_blocking(_ensure_directory, root, root)
    try:
        api_tree_names = await _async_list_trees(client, context)
    except Exception as exc:
        raise _with_tree_path(exc, "")
    if tree_names:
        api_tree_names = [name for name in api_tree_names if name in tree_names]
    if not api_tree_names:
        raise HttpNotFoundError("One or more Parameter trees not found")
    for name in api_tree_names:
        _safe_name(name, "")
    blobs = await _async_blob_urls(client, api_tree_names, context)
    for name in api_tree_names:
        await _async_download_tree(
            client, name, root, delete_existing_trees, blobs, context
        )
