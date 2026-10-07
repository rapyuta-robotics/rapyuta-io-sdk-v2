"""Parameter filesystem API contract tests using httpx MockTransport."""

from __future__ import annotations

import base64
import asyncio
import hashlib
import json
import threading

import httpx
import pytest

from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.context import RequestContext
from rapyuta_io_sdk_v2.exceptions import BadRequestError
from rapyuta_io_sdk_v2.async_client import AsyncClient
from rapyuta_io_sdk_v2.client import Client
from rapyuta_io_sdk_v2.parameter_operations import ParameterPathError


HOST = "https://core.test"


class AsyncMockTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler):
        self.handler = handler

    async def handle_async_request(self, request):
        return await self.handler(request)


def make_sync_parameter_client(
    transport: httpx.BaseTransport, headers=None, auth=None
) -> Client:
    config = Configuration(
        load_cli_config=False,
        auth_token="token",
        project_guid="project",
        core_api_host=HOST,
    )
    http_client = httpx.Client(transport=transport, headers=headers, auth=auth)
    return Client(config, transport=http_client)


def make_async_parameter_client(
    transport: httpx.AsyncBaseTransport, headers=None
) -> AsyncClient:
    config = Configuration(
        load_cli_config=False,
        auth_token="token",
        project_guid="project",
        core_api_host=HOST,
    )
    http_client = httpx.AsyncClient(transport=transport, headers=headers)
    return AsyncClient(config, transport=http_client)


def _json(data, status=200):
    return httpx.Response(status, json={"data": data})


def test_upload_default_folder_json_and_tree_filter(tmp_path):
    selected = tmp_path / "selected"
    selected.mkdir()
    (selected / "config.json").write_text('{"a": 1}', encoding="utf-8")
    (selected / "nested").mkdir()
    (selected / "nested" / "readme.txt").write_text("hello", encoding="utf-8")
    ignored = tmp_path / "ignored"
    ignored.mkdir()

    seen = []

    def handler(request):
        seen.append(request)
        return _json({})

    client = make_sync_parameter_client(httpx.MockTransport(handler))
    client.upload_configurations(tmp_path, tree_names=["selected"])
    client.c.close()

    assert [r.url.path for r in seen] == [
        "/api/paramserver/tree/selected",
        "/api/paramserver/tree/selected/config.json",
        "/api/paramserver/tree/selected/nested",
        "/api/paramserver/binaryfilenode/selected/nested/readme.txt",
    ]
    assert [json.loads(r.content) for r in seen[:3]] == [
        {"type": "ValueNode"},
        {"type": "FileNode", "data": '{"a": 1}', "contentType": "application/json"},
        {"type": "FolderNode"},
    ]
    assert seen[3].headers["checksum"] == hashlib.md5(b"hello").hexdigest()
    assert all(r.headers["authorization"] == "Bearer token" for r in seen)


def test_upload_accepts_v1_null_node_mutation_responses(tmp_path):
    (tmp_path / "tree").mkdir()
    client = make_sync_parameter_client(
        httpx.MockTransport(lambda request: httpx.Response(200, json=None))
    )
    client.upload_configurations(tmp_path)
    client.c.close()


def test_upload_legacy_attribute_value_layout(tmp_path):
    tree = tmp_path / "robot"
    tree.mkdir()
    (tree / "direct.yaml").write_text("value: direct")
    (tree / "attribute").mkdir()
    (tree / "attribute" / "ignored.txt").write_text("ignored")
    (tree / "attribute" / "value").mkdir()
    (tree / "attribute" / "value" / "nested.yaml").write_text("value: nested")
    seen = []

    def handler(request):
        seen.append((request.url.path, json.loads(request.content)))
        return _json({})

    client = make_sync_parameter_client(httpx.MockTransport(handler))
    client.upload_configurations(tmp_path, as_folder=False)
    client.c.close()
    assert seen == [
        ("/api/paramserver/tree/robot", {"type": "ValueNode"}),
        ("/api/paramserver/tree/robot/attribute", {"type": "AttributeNode"}),
        ("/api/paramserver/tree/robot/attribute/value", {"type": "ValueNode"}),
        (
            "/api/paramserver/tree/robot/attribute/value/nested.yaml",
            {"type": "FileNode", "data": "value: nested", "contentType": "text/yaml"},
        ),
        (
            "/api/paramserver/tree/robot/direct.yaml",
            {"type": "FileNode", "data": "value: direct", "contentType": "text/yaml"},
        ),
    ]


def test_binary_upload_uses_signed_block_blob_without_auth_leak(tmp_path):
    tree = tmp_path / "tree"
    tree.mkdir()
    payload = b"opaque-binary"
    (tree / "data.bin").write_bytes(payload)
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.host == "storage.test":
            return httpx.Response(201)
        if request.method == "PUT" and "binaryfilenode" in request.url.path:
            return _json({"blobRefId": "blob-1", "uploadUrl": "https://storage.test/sas"})
        return _json({})

    client = make_sync_parameter_client(
        httpx.MockTransport(handler),
        headers={"Authorization": "external-default"},
        auth=httpx.BasicAuth("transport-user", "transport-password"),
    )
    client.upload_configurations(tmp_path)
    client.c.close()

    binary = next(r for r in seen if "binaryfilenode" in r.url.path)
    signed = next(r for r in seen if r.url.host == "storage.test")
    commit = next(r for r in seen if r.method == "PATCH")
    assert binary.headers["checksum"] == hashlib.md5(payload).hexdigest()
    assert signed.content == payload
    assert signed.headers["x-ms-blob-type"] == "BlockBlob"
    assert (
        signed.headers["x-ms-blob-content-md5"]
        == base64.b64encode(hashlib.md5(payload).digest()).decode()
    )
    assert "authorization" not in signed.headers
    assert "external-default" not in str(signed.headers)
    assert commit.url.path.endswith("/tree/blobref/blob-1")


def test_upload_inline_payload_threshold_and_delete_existing(tmp_path):
    tree = tmp_path / "tree"
    tree.mkdir()
    large = "x" * (128 * 1024)
    (tree / "large.json").write_text(json.dumps(large))
    seen = []

    def handler(request):
        seen.append(request)
        if "binaryfilenode" in request.url.path:
            return _json({})
        return _json({})

    client = make_sync_parameter_client(httpx.MockTransport(handler))
    client.upload_configurations(tmp_path, delete_existing_trees=True)
    client.c.close()
    assert seen[0].method == "DELETE"
    assert seen[1].method == "PUT" and seen[1].url.path.endswith("/tree")
    assert any("binaryfilenode" in request.url.path for request in seen)


def test_oversized_yaml_binary_uses_octet_stream_content_type(tmp_path):
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "large.yaml").write_text("value: " + "x" * (128 * 1024))
    seen = []

    def handler(request):
        seen.append(request)
        return _json({})

    client = make_sync_parameter_client(httpx.MockTransport(handler))
    client.upload_configurations(tmp_path)
    client.c.close()
    binary = next(request for request in seen if "binaryfilenode" in request.url.path)
    assert binary.headers["content-type"] == "application/octet-stream"


def test_upload_failure_attaches_tree_path(tmp_path):
    tree = tmp_path / "bad"
    tree.mkdir()
    (tree / "file.txt").write_text("body")

    def handler(request):
        if request.url.path.endswith("file.txt"):
            return httpx.Response(400, json={"error": "invalid node"})
        return _json({})

    client = make_sync_parameter_client(httpx.MockTransport(handler))
    with pytest.raises(BadRequestError) as error:
        client.upload_configurations(tmp_path)
    client.c.close()
    assert error.value.tree_path == "bad/file.txt"


def test_download_writes_inline_tree_and_rejects_unsafe_server_names(tmp_path):
    def handler(request):
        if request.url.path.endswith("/tree"):
            return _json(["robot"])
        if request.url.path.endswith("treeblobs"):
            return _json({"blobRefs": []})
        return _json(
            {
                "type": "ValueNode",
                "name": "robot",
                "children": [{"type": "FileNode", "name": "config.yaml", "data": "a: b"}],
            }
        )

    client = make_sync_parameter_client(httpx.MockTransport(handler))
    client.download_configurations(tmp_path)
    client.c.close()
    assert (tmp_path / "robot" / "config.yaml").read_text() == "a: b"

    unsafe_client = make_sync_parameter_client(
        httpx.MockTransport(
            lambda request: (
                _json(["../escape"])
                if request.url.path.endswith("/tree")
                else _json({"blobRefs": []})
            )
        )
    )
    with pytest.raises(ParameterPathError):
        unsafe_client.download_configurations(tmp_path / "unsafe")
    unsafe_client.c.close()
    assert not (tmp_path / "escape").exists()


def test_download_rejects_windows_drive_relative_tree_before_deleting_root(tmp_path):
    def handler(request):
        if request.url.path.endswith("/tree"):
            return _json(["C:"])
        return _json({"blobRefs": []})

    client = make_sync_parameter_client(httpx.MockTransport(handler))
    marker = tmp_path / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(ParameterPathError):
        client.download_configurations(tmp_path, delete_existing_trees=True)
    client.c.close()
    assert marker.read_text() == "keep"


def test_download_get_error_preserves_existing_tree_when_delete_requested(tmp_path):
    tree = tmp_path / "robot"
    tree.mkdir()
    marker = tree / "keep.txt"
    marker.write_text("keep")

    def handler(request):
        if request.url.path.endswith("/tree"):
            return _json(["robot"])
        if request.url.path.endswith("treeblobs"):
            return _json({"blobRefs": []})
        return httpx.Response(404, json={"error": "tree missing"})

    client = make_sync_parameter_client(httpx.MockTransport(handler))
    with pytest.raises(Exception, match="tree missing") as error:
        client.download_configurations(tmp_path, delete_existing_trees=True)
    client.c.close()
    assert error.value.tree_path == "robot"
    assert marker.read_text() == "keep"


def test_download_signed_blob_streams_without_platform_headers(tmp_path):
    payload = b"large file"

    def handler(request):
        if request.url.host == "storage.test":
            assert "authorization" not in request.headers
            return httpx.Response(200, content=payload)
        if request.url.path.endswith("/tree"):
            return _json(["robot"])
        if request.url.path.endswith("treeblobs"):
            return _json(
                {"blobRefs": [{"ID": "blob-1", "signedUrl": "https://storage.test/file"}]}
            )
        return _json(
            {
                "type": "ValueNode",
                "name": "robot",
                "children": [
                    {"type": "FileNode", "name": "data.bin", "blobRefId": "blob-1"}
                ],
            }
        )

    client = make_sync_parameter_client(
        httpx.MockTransport(handler), headers={"Authorization": "must-not-leak"}
    )
    client.download_configurations(tmp_path)
    client.c.close()
    assert (tmp_path / "robot" / "data.bin").read_bytes() == payload


def test_signed_blob_http_error_is_mapped_after_reading_stream_body(tmp_path):
    class ErrorBody(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"error":"expired signed url"}'

    def handler(request):
        if request.url.host == "storage.test":
            return httpx.Response(403, stream=ErrorBody())
        if request.url.path.endswith("/tree"):
            return _json(["robot"])
        if request.url.path.endswith("treeblobs"):
            return _json(
                {"blobRefs": [{"ID": 1, "signedUrl": "https://storage.test/blob"}]}
            )
        return _json(
            {
                "type": "ValueNode",
                "name": "robot",
                "children": [{"type": "FileNode", "name": "data.bin", "blobRefId": "1"}],
            }
        )

    client = make_sync_parameter_client(httpx.MockTransport(handler))
    with pytest.raises(Exception, match="expired signed url") as error:
        client.download_configurations(tmp_path)
    client.c.close()
    assert error.value.status_code == 403
    assert error.value.tree_path == "robot"


@pytest.mark.asyncio
async def test_async_upload_and_download_use_native_async_transport(tmp_path):
    tree = tmp_path / "robot"
    tree.mkdir()
    (tree / "config.json").write_text('{"ok": true}')
    seen = []

    async def handler(request):
        seen.append(request)
        if request.url.path.endswith("/tree") and request.method == "GET":
            return _json(["from-api"])
        if request.url.path.endswith("treeblobs"):
            return _json({"blobRefs": []})
        if request.url.path.endswith("from-api") and request.method == "GET":
            return _json(
                {
                    "type": "ValueNode",
                    "name": "from-api",
                    "children": [
                        {"type": "FileNode", "name": "x.txt", "data": "downloaded"}
                    ],
                }
            )
        return _json({})

    client = make_async_parameter_client(AsyncMockTransport(handler))
    context = RequestContext(request_id="parameter-test")
    await client.upload_configurations(tmp_path, context=context)
    await client.download_configurations(
        tmp_path, tree_names=["from-api"], context=context
    )
    await client.c.aclose()
    assert (tmp_path / "from-api" / "x.txt").read_text() == "downloaded"
    assert any(r.headers.get("x-request-id") == "parameter-test" for r in seen)


@pytest.mark.asyncio
async def test_async_download_signed_blob_does_not_leak_client_authorization(tmp_path):
    payload = b"async blob"

    async def handler(request):
        if request.url.host == "storage.test":
            assert "authorization" not in request.headers
            return httpx.Response(200, content=payload)
        if request.url.path.endswith("/tree"):
            return _json(["robot"])
        if request.url.path.endswith("treeblobs"):
            return _json(
                {"blobRefs": [{"ID": "b", "signedUrl": "https://storage.test/blob"}]}
            )
        return _json(
            {
                "type": "ValueNode",
                "name": "robot",
                "children": [{"type": "FileNode", "name": "data.bin", "blobRefId": "b"}],
            }
        )

    client = make_async_parameter_client(
        AsyncMockTransport(handler), headers={"Authorization": "external-default"}
    )
    await client.download_configurations(tmp_path)
    await client.c.aclose()
    assert (tmp_path / "robot" / "data.bin").read_bytes() == payload


@pytest.mark.asyncio
async def test_async_download_get_error_preserves_existing_tree(tmp_path):
    tree = tmp_path / "robot"
    tree.mkdir()
    marker = tree / "keep.txt"
    marker.write_text("keep")

    async def handler(request):
        if request.url.path.endswith("/tree"):
            return _json(["robot"])
        if request.url.path.endswith("treeblobs"):
            return _json({"blobRefs": []})
        return httpx.Response(404, json={"error": "tree missing"})

    client = make_async_parameter_client(AsyncMockTransport(handler))
    with pytest.raises(Exception, match="tree missing") as error:
        await client.download_configurations(tmp_path, delete_existing_trees=True)
    await client.c.aclose()
    assert error.value.tree_path == "robot"
    assert marker.read_text() == "keep"


@pytest.mark.asyncio
async def test_async_blob_download_cancellation_removes_temporary_file(tmp_path):
    started = asyncio.Event()
    never = asyncio.Event()

    class SlowBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            started.set()
            yield b"partial"
            await never.wait()

    async def handler(request):
        if request.url.host == "storage.test":
            return httpx.Response(200, stream=SlowBody())
        if request.url.path.endswith("/tree"):
            return _json(["robot"])
        if request.url.path.endswith("treeblobs"):
            return _json(
                {"blobRefs": [{"ID": 8, "signedUrl": "https://storage.test/blob"}]}
            )
        return _json(
            {
                "type": "ValueNode",
                "name": "robot",
                "children": [{"type": "FileNode", "name": "data.bin", "blobRefId": "8"}],
            }
        )

    client = make_async_parameter_client(AsyncMockTransport(handler))
    task = asyncio.create_task(client.download_configurations(tmp_path))
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await client.c.aclose()
    assert not (tmp_path / "robot" / "data.bin").exists()
    assert list((tmp_path / "robot").glob(".*.tmp")) == []


@pytest.mark.asyncio
async def test_async_cancel_during_temp_creation_removes_temp_file(tmp_path, monkeypatch):
    import rapyuta_io_sdk_v2.parameter_operations as parameter_operations

    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    release = threading.Event()
    original_create = parameter_operations._create_temp_file

    def slow_create(directory, filename):
        name = original_create(directory, filename)
        loop.call_soon_threadsafe(started.set)
        release.wait(timeout=3)
        return name

    monkeypatch.setattr(parameter_operations, "_create_temp_file", slow_create)

    async def handler(request):
        if request.url.path.endswith("/tree"):
            return _json(["robot"])
        if request.url.path.endswith("treeblobs"):
            return _json({"blobRefs": []})
        return _json(
            {
                "type": "ValueNode",
                "name": "robot",
                "children": [
                    {"type": "FileNode", "name": "config.txt", "data": "inline"}
                ],
            }
        )

    client = make_async_parameter_client(AsyncMockTransport(handler))
    task = asyncio.create_task(client.download_configurations(tmp_path))
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await client.c.aclose()
    assert list((tmp_path / "robot").glob(".*.tmp")) == []
