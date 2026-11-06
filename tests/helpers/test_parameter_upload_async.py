# Copyright 2026 Rapyuta Robotics

from __future__ import annotations

import asyncio
import base64
import hashlib
import threading
from functools import partial
from http import HTTPStatus
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import httpx
import pytest
import pytest_asyncio

from rapyuta_io_sdk_v2 import AsyncClient, Configuration, ParameterUploadOptions
from rapyuta_io_sdk_v2.exceptions import ParameterUploadCancelled, ParameterUploadError
from rapyuta_io_sdk_v2.helpers import _parameter_source as source_module
from rapyuta_io_sdk_v2.helpers import _parameter_storage as storage_module
from rapyuta_io_sdk_v2.helpers import async_parameter as helper_module
from rapyuta_io_sdk_v2.helpers import upload_parameters_async
from rapyuta_io_sdk_v2.helpers._parameter_upload import disk_work
from tests.data.parameter_data import (
    check_media_headers,
    media_source,
    signed_query_error,
)
from tests.data.parameter_failures import (
    assert_failed_submission,
    corrupt_chunk,
    reject_blocklist,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from tests.data.parameter_data import ParameterService


DUPLICATE_ERROR = "blobRef signed url not generated or blobRef already uploaded"
LEGACY_FILES = 2
READ_ARGUMENT_COUNT = 2
TOTAL_FILES = 100
FILES_PER_TREE = 50
UNIQUE_BLOBS = 25
LINK_COUNT = 2


@pytest_asyncio.fixture
async def target(
    service: ParameterService,
) -> AsyncIterator[tuple[AsyncClient, httpx.AsyncClient]]:
    instance = AsyncClient(
        Configuration(
            auth_token="token", project_guid="project", core_api_host="https://core"
        )
    )
    await instance.c.aclose()
    instance.c = httpx.AsyncClient(transport=httpx.MockTransport(service.platform))
    storage = httpx.AsyncClient(transport=httpx.MockTransport(service.storage))
    yield instance, storage
    await instance.c.aclose()
    await storage.aclose()
    instance.sync_client.close()


@pytest.mark.asyncio
async def test_upload_mixed_source(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    source: Path,
    service: ParameterService,
) -> None:
    client, storage = target
    result = await upload_parameters_async(client, source, storage_client=storage)
    assert result.completed_trees == ("alpha", "beta")
    assert len(result.completed_files) == TOTAL_FILES
    assert "alpha/empty" in result.created_directories
    assert result.skipped_entries[0].reason == "root_file"
    assert service.nodes["alpha/one"]["type"] == "FolderNode"
    assert (
        service.nodes["alpha/one/two/three/four/five/file1.yaml"]["data"]
        == "key: café\r\n"
    )
    assert len(service.content) == UNIQUE_BLOBS
    assert not client.c.is_closed
    assert not storage.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "names", [("alpha",), ("alpha", "missing"), ("alpha", "alpha")]
)
async def test_exact_selection(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    source: Path,
    names: tuple[str, ...],
) -> None:
    client, storage = target
    result = await upload_parameters_async(
        client,
        source,
        options=ParameterUploadOptions(tree_names=names),
        storage_client=storage,
    )
    assert result.selected_trees == ("alpha",)
    assert result.completed_trees == ("alpha",)
    assert len(result.completed_files) == FILES_PER_TREE
    assert any(
        entry.reason == "unmatched_tree" for entry in result.skipped_entries
    ) == ("missing" in names)


@pytest.mark.asyncio
async def test_no_matches_fail_before_mutation(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    source: Path,
    service: ParameterService,
) -> None:
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        await upload_parameters_async(
            client,
            source,
            options=ParameterUploadOptions(tree_names=("missing",)),
            storage_client=storage,
        )
    assert caught.value.failure.stage == "validate_source"
    assert service.requests == []


@pytest.mark.asyncio
async def test_empty_source_noop(
    *, target: tuple[AsyncClient, httpx.AsyncClient], tmp_path: Path
) -> None:
    client, storage = target
    (tmp_path / "loose").write_bytes(b"ignored")
    result = await upload_parameters_async(client, tmp_path, storage_client=storage)
    assert result.selected_trees == ()
    assert result.completed_trees == ()
    assert result.skipped_entries[0].path == "loose"


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["bad name.txt", ".hidden", "a" * 51])
async def test_preflight_rejects_backend_names(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    source: Path,
    service: ParameterService,
    filename: str,
) -> None:
    (source / "alpha" / filename).write_bytes(b"data")
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        await upload_parameters_async(client, source, storage_client=storage)
    assert caught.value.failure.stage == "validate_source"
    assert service.requests == []


@pytest.mark.asyncio
async def test_links_are_skipped(
    *, target: tuple[AsyncClient, httpx.AsyncClient], source: Path
) -> None:
    (source / "linked").symlink_to(source / "alpha", target_is_directory=True)
    (source / "alpha" / "link.bin").symlink_to(source / "loose.txt")
    client, storage = target
    result = await upload_parameters_async(client, source, storage_client=storage)
    assert (
        sum(entry.reason == "symbolic_link" for entry in result.skipped_entries)
        == LINK_COUNT
    )
    assert len(result.completed_files) == TOTAL_FILES


@pytest.mark.asyncio
async def test_transfer_failure_exposes_progress(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    source: Path,
    service: ParameterService,
) -> None:
    client, storage = target
    service.reject = ("PATCH", "/api/paramserver/binaryfilenode/alpha/blobref/1", 500)
    with pytest.raises(ParameterUploadError) as caught:
        await upload_parameters_async(client, source, storage_client=storage)
    error = caught.value
    assert error.failure.stage == "confirm_upload"
    assert error.failure.path.endswith("file0.bin")
    assert error.partial_result.created_directories
    assert error.partial_result.completed_files == ()
    assert error.partial_result.completed_trees == ()
    assert error.__cause__ is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers", [{"Authorization": "secret"}, {"project": "project"}]
)
async def test_unsafe_storage_rejected(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    source: Path,
    service: ParameterService,
    headers: dict[str, str],
) -> None:
    client, storage = target
    storage.headers.update(headers)
    with pytest.raises(ParameterUploadError):
        await upload_parameters_async(client, source, storage_client=storage)
    assert service.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload", [b"[not a mapping]", b"key: [" + "é".encode() * 22000]
)
async def test_invalid_candidates_validate_before_size(
    *, target: tuple[AsyncClient, httpx.AsyncClient], tmp_path: Path, payload: bytes
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "file.yaml").write_bytes(payload)
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        await upload_parameters_async(client, tmp_path, storage_client=storage)
    assert caught.value.failure.stage == "read_file"
    assert caught.value.partial_result.completed_files == ()


@pytest.mark.asyncio
async def test_large_invalid_structured_file_uses_blob(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    tmp_path: Path,
    service: ParameterService,
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    payload = b"[invalid" + b"x" * 131072
    (tree / "file.yaml").write_bytes(payload)
    client, storage = target
    result = await upload_parameters_async(client, tmp_path, storage_client=storage)
    assert result.completed_files[0].storage == "blob"
    assert service.content[1] == payload


@pytest.mark.asyncio
async def test_cancellation_preserves_completed_identities(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    source: Path,
    service: ParameterService,
) -> None:

    client, storage = target
    reached = asyncio.Event()
    release = asyncio.Event()

    async def platform(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/paramserver/tree/beta":
            reached.set()
            await release.wait()
        return service.platform(request)

    await client.c.aclose()
    client.c = httpx.AsyncClient(transport=httpx.MockTransport(platform))
    task = asyncio.create_task(
        upload_parameters_async(client, source, storage_client=storage)
    )
    await asyncio.wait_for(reached.wait(), 5)
    task.cancel()
    with pytest.raises(ParameterUploadCancelled) as caught:
        await task
    result = caught.value.partial_result
    assert caught.value.failure.path == "beta"
    assert caught.value.failure.stage == "create_tree"
    assert result.completed_trees == ("alpha",)
    assert len(result.completed_files) == FILES_PER_TREE
    assert result.created_directories
    assert result.skipped_entries
    assert task.cancelled()
    assert "beta" not in service.nodes
    assert not storage.is_closed


@pytest.mark.asyncio
async def test_disk_workers_leave_event_loop_responsive() -> None:

    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def local_work() -> None:
        started.set()
        release.wait(timeout=5)
        finished.set()

    task = asyncio.create_task(disk_work(local_work))
    assert await asyncio.to_thread(started.wait, 5)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        ("/tree/alpha", "create_tree"),
        ("/tree/alpha/empty", "create_node"),
        ("/binaryfilenode/alpha/one/two/three/four/five/file0.bin", "prepare_upload"),
    ],
)
async def test_platform_failure_stage(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    source: Path,
    service: ParameterService,
    case: tuple[str, str],
) -> None:
    path, stage = case
    service.reject = ("PUT", "/api/paramserver" + path, 500)
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        await upload_parameters_async(client, source, storage_client=storage)
    assert caught.value.failure.stage == stage
    assert caught.value.partial_result.completed_trees == ()
    assert "beta" not in service.nodes


@pytest.mark.asyncio
async def test_storage_failure_never_confirms(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    source: Path,
    service: ParameterService,
) -> None:
    client, storage = target
    await storage.aclose()
    storage = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(500))
    )
    try:
        with pytest.raises(ParameterUploadError) as caught:
            await upload_parameters_async(client, source, storage_client=storage)
        assert caught.value.failure.stage == "transfer_blob"
        assert caught.value.partial_result.completed_files == ()
        assert all(request.method != "PATCH" for request in service.requests)
        assert "a%2Bb" not in str(caught.value)
    finally:
        await storage.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("uploaded", [False, True])
async def test_url_less_prepare_requires_uploaded_reference(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    tmp_path: Path,
    service: ParameterService,
    uploaded: bool,
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "file.bin").write_bytes(b"binary")
    client, storage = target

    def platform(request: httpx.Request) -> httpx.Response:
        response = service.platform(request)
        if "/binaryfilenode/" in request.url.path:
            payload = response.json()
            payload["data"].pop("uploadUrl", None)
            service.blobs[1]["status"] = "Uploaded" if uploaded else "Pending"
            return httpx.Response(201, json=payload)
        return response

    await client.c.aclose()
    client.c = httpx.AsyncClient(transport=httpx.MockTransport(platform))
    if uploaded:
        result = await upload_parameters_async(client, tmp_path, storage_client=storage)
        assert len(result.completed_files) == 1
    else:
        with pytest.raises(ParameterUploadError) as caught:
            await upload_parameters_async(client, tmp_path, storage_client=storage)
        assert caught.value.failure.stage == "verify_blob"
    assert not any(request.url.host == "storage" for request in service.requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [(403, True), (403, False), (400, True)])
async def test_ambiguous_commit_verifies_status(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    tmp_path: Path,
    service: ParameterService,
    case: tuple[int, bool],
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "file.bin").write_bytes(b"binary")
    client, storage = target
    status, uploaded = case

    def platform(request: httpx.Request) -> httpx.Response:
        response = service.platform(request)
        if request.method == "PATCH":
            service.blobs[1]["status"] = "Uploaded" if uploaded else "Pending"
            return httpx.Response(
                status,
                json={"error": DUPLICATE_ERROR},
            )
        return response

    await client.c.aclose()
    client.c = httpx.AsyncClient(transport=httpx.MockTransport(platform))
    if status == HTTPStatus.FORBIDDEN and uploaded:
        result = await upload_parameters_async(client, tmp_path, storage_client=storage)
        assert len(result.completed_files) == 1
    else:
        with pytest.raises(ParameterUploadError) as caught:
            await upload_parameters_async(client, tmp_path, storage_client=storage)
        assert caught.value.failure.stage == "confirm_upload"
        assert caught.value.partial_result.completed_files == ()
        assert str(caught.value.__cause__) == DUPLICATE_ERROR


@pytest.mark.asyncio
async def test_changed_source_after_preparation_never_confirms(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    tmp_path: Path,
    service: ParameterService,
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    path = tree / "file.bin"
    path.write_bytes(b"binary")
    client, storage = target

    def platform(request: httpx.Request) -> httpx.Response:
        response = service.platform(request)
        if "/binaryfilenode/" in request.url.path:
            path.write_bytes(b"changed")
        return response

    await client.c.aclose()
    client.c = httpx.AsyncClient(transport=httpx.MockTransport(platform))
    with pytest.raises(ParameterUploadError) as caught:
        await upload_parameters_async(client, tmp_path, storage_client=storage)
    assert caught.value.failure.stage == "transfer_blob"
    assert all(request.method != "PATCH" for request in service.requests)


@pytest.mark.asyncio
async def test_recreation_only_replaces_selected_tree(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    source: Path,
    service: ParameterService,
) -> None:
    client, storage = target
    await upload_parameters_async(client, source, storage_client=storage)
    service.nodes["alpha/remote.bin"] = {"type": "FileNode"}
    service.nodes["beta/remote.bin"] = {"type": "FileNode"}
    with pytest.raises(ParameterUploadError) as caught:
        await upload_parameters_async(client, source, storage_client=storage)
    assert caught.value.failure.stage == "create_tree"
    assert "alpha/remote.bin" in service.nodes
    options = ParameterUploadOptions(tree_names=("alpha",), delete_existing_trees=True)
    result = await upload_parameters_async(
        client, source, options=options, storage_client=storage
    )
    assert result.deleted_trees == ("alpha",)
    assert "alpha/remote.bin" not in service.nodes
    assert "beta/remote.bin" in service.nodes
    assert result.completed_trees == ("alpha",)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["delete_tree", "create_tree"])
async def test_recreation_failure_preserves_deletions(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    source: Path,
    service: ParameterService,
    stage: str,
) -> None:
    verb = "DELETE" if stage == "delete_tree" else "PUT"
    service.reject = (verb, "/api/paramserver/tree/alpha", 500)
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        await upload_parameters_async(
            client,
            source,
            options=ParameterUploadOptions(delete_existing_trees=True),
            storage_client=storage,
        )
    assert caught.value.failure.stage == stage
    expected = ("alpha",) if stage == "create_tree" else ()
    assert caught.value.partial_result.deleted_trees == expected
    assert service.nodes == {}
    assert all("beta" not in request.url.path for request in service.requests)


@pytest.mark.asyncio
async def test_legacy_hierarchy_and_attribute_file_skips(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    tmp_path: Path,
    service: ParameterService,
) -> None:
    tree = tmp_path / "tree"
    parent = tree / "attribute" / "value" / "second" / "value"
    parent.mkdir(parents=True)
    (tree / "attribute" / "skip.bin").write_bytes(b"skip")
    (tree / "file.yaml").write_bytes(b"key: value\r\n")
    large = b"[invalid" + b"x" * 131072
    (parent / "large.json").write_bytes(large)
    client, storage = target
    result = await upload_parameters_async(
        client,
        tmp_path,
        options=ParameterUploadOptions(as_folder=False),
        storage_client=storage,
    )
    assert service.nodes["tree/attribute"]["type"] == "AttributeNode"
    assert service.nodes["tree/attribute/value"]["type"] == "ValueNode"
    assert service.content[1] == large
    assert len(result.completed_files) == LEGACY_FILES
    assert result.skipped_entries[0].reason == "legacy_attribute_file"
    assert result.skipped_entries[0].path == "tree/attribute/skip.bin"
    assert (
        sum(request.url.path.endswith("large.json") for request in service.requests)
        == 1
    )


@pytest.mark.asyncio
async def test_known_legacy_restriction_fails_preflight(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    tmp_path: Path,
    service: ParameterService,
) -> None:
    (tmp_path / "tree" / "one").mkdir(parents=True)
    (tmp_path / "tree" / "two").mkdir()
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        await upload_parameters_async(
            client,
            tmp_path,
            options=ParameterUploadOptions(as_folder=False),
            storage_client=storage,
        )
    assert caught.value.failure.stage == "validate_source"
    assert service.requests == []


@pytest.mark.asyncio
async def test_cancellation_after_recreation_reports_deletion(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    source: Path,
    service: ParameterService,
) -> None:
    client, storage = target
    reached = asyncio.Event()
    release = asyncio.Event()

    async def platform(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "PUT"
            and request.url.path == "/api/paramserver/tree/alpha"
        ):
            reached.set()
            await release.wait()
        return service.platform(request)

    await client.c.aclose()
    client.c = httpx.AsyncClient(transport=httpx.MockTransport(platform))
    task = asyncio.create_task(
        upload_parameters_async(
            client,
            source,
            options=ParameterUploadOptions(delete_existing_trees=True),
            storage_client=storage,
        )
    )
    await asyncio.wait_for(reached.wait(), 5)
    task.cancel()
    with pytest.raises(ParameterUploadCancelled) as caught:
        await task
    assert caught.value.partial_result.deleted_trees == ("alpha",)
    assert caught.value.partial_result.completed_trees == ()
    assert caught.value.partial_result.skipped_entries
    assert task.cancelled()
    assert all("beta" not in request.url.path for request in service.requests)


@pytest.mark.asyncio
async def test_prehash_cancellation_stops_before_next_block(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "file.bin").write_bytes(b"z" * (source_module.BLOCK_SIZE * 3))
    original = source_module.read_chunk
    started = threading.Event()
    release = threading.Event()
    offsets = []

    def blocking_read(*args: object) -> bytes:
        if len(args) == READ_ARGUMENT_COUNT:
            offsets.append(args[1])
            started.set()
            release.wait(timeout=5)
        return original(*args)

    monkeypatch.setattr(source_module, "read_chunk", blocking_read)
    client, storage = target
    task = asyncio.create_task(
        upload_parameters_async(client, tmp_path, storage_client=storage)
    )
    assert await asyncio.to_thread(started.wait, 5)
    task.cancel()
    release.set()
    with pytest.raises(ParameterUploadCancelled) as caught:
        await task
    assert offsets == [0]
    assert caught.value.failure.stage == "read_file"
    assert caught.value.partial_result.created_directories == ("tree",)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        (operation, error_type)
        for operation in ("lstat", "open")
        for error_type in (FileNotFoundError, PermissionError)
    ],
)
async def test_preflight_os_error_identifies_child(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    tmp_path: Path,
    service: ParameterService,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[str, type[OSError]],
) -> None:
    operation, error_type = case
    (tmp_path / "tree").mkdir()
    file = tmp_path / "tree/file.bin"
    file.write_bytes(b"data")
    error = error_type("source unavailable")
    error.filename = str(file)
    original = getattr(type(tmp_path), operation)

    def inspect(path: Path, *args: object, **kwargs: object) -> object:
        if path == file:
            raise error
        return original(path, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), operation, inspect)
    with pytest.raises(ParameterUploadError) as caught:
        await upload_parameters_async(
            target[0],
            tmp_path,
            options=ParameterUploadOptions(delete_existing_trees=True),
            storage_client=target[1],
        )
    assert caught.value.failure.path in {str(file), "tree/file.bin"}
    assert caught.value.failure.stage == "validate_source"
    assert caught.value.__cause__ is error
    assert caught.value.partial_result.completed_files == ()
    assert caught.value.partial_result.deleted_trees == ()
    assert caught.value.partial_result.model_config["frozen"]
    assert service.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("scheme", ["HTTPS", "HtTpS"])
@pytest.mark.parametrize("scenario", ["platform", "malformed", "verification"])
async def test_failure_redacts_signed_query(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    tmp_path: Path,
    service: ParameterService,
    scheme: str,
    scenario: str,
) -> None:
    (tmp_path / "tree").mkdir()
    (tmp_path / "tree/file.bin").write_bytes(b"binary")
    client, storage = target
    platform = partial(signed_query_error, service, scenario=scenario, scheme=scheme)

    await client.c.aclose()
    client.c = httpx.AsyncClient(transport=httpx.MockTransport(platform))
    with pytest.raises(ParameterUploadError) as caught:
        await upload_parameters_async(client, tmp_path, storage_client=storage)
    assert "fake-secret" not in caught.value.failure.message
    assert "fake-secret" not in str(caught.value)
    if scenario == "verification":
        assert "fake-secret" not in str(caught.value.__cause__.__notes__)
        assert "fake-secret" in str(caught.value.__cause__.__cause__)
    else:
        assert "fake-secret" in str(caught.value.__cause__)
        assert all(request.method != "PATCH" for request in service.requests)
    assert caught.value.partial_result.completed_files == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        (failure, ownership)
        for failure in ("corruption", "blocklist")
        for ownership in ("owned", "injected")
    ],
)
async def test_storage_failure_preserves_progress_and_ownership(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    failure_source: Path,
    service: ParameterService,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[str, str],
) -> None:
    failure, ownership = case
    if failure == "corruption":
        monkeypatch.setattr(storage_module, "read_chunk", corrupt_chunk)
    storage = httpx.AsyncClient(
        transport=httpx.MockTransport(partial(reject_blocklist, service)),
        follow_redirects=False,
        trust_env=False,
    )
    constructor = Mock(return_value=storage)
    monkeypatch.setattr(
        helper_module, "httpx", SimpleNamespace(AsyncClient=constructor)
    )
    try:
        with pytest.raises(ParameterUploadError) as caught:
            await upload_parameters_async(
                target[0],
                failure_source,
                storage_client=storage if ownership == "injected" else None,
            )
        assert_failed_submission(caught.value, service)
        expected = ValueError if failure == "corruption" else httpx.HTTPStatusError
        assert isinstance(caught.value.__cause__, expected)
        assert [
            request.url.params.get("comp")
            for request in service.requests
            if request.url.host == "storage"
        ] == (
            ["block", "block"]
            if failure == "corruption"
            else ["block", "block", "blocklist"]
        )
        assert storage.is_closed == (ownership == "owned")
        assert not target[0].c.is_closed
        assert not target[1].is_closed
        if ownership == "owned":
            constructor.assert_called_once_with(follow_redirects=False, trust_env=False)
        else:
            constructor.assert_not_called()
    finally:
        await storage.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("ownership", ["owned", "injected"])
async def test_storage_cancellation_closes_only_owned_client(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    failure_source: Path,
    service: ParameterService,
    monkeypatch: pytest.MonkeyPatch,
    ownership: str,
) -> None:
    reached, release = asyncio.Event(), asyncio.Event()

    async def respond(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("comp") == "blocklist":
            service.requests.append(request)
            reached.set()
            await release.wait()
        return service.storage(request)

    storage = httpx.AsyncClient(
        transport=httpx.MockTransport(respond), follow_redirects=False, trust_env=False
    )
    constructor = Mock(return_value=storage)
    monkeypatch.setattr(
        helper_module, "httpx", SimpleNamespace(AsyncClient=constructor)
    )
    task = asyncio.create_task(
        upload_parameters_async(
            target[0],
            failure_source,
            storage_client=storage if ownership == "injected" else None,
        )
    )
    try:
        await asyncio.wait_for(reached.wait(), 5)
        task.cancel("Cancelled HTTPS://storage/blob?sig=fake-secret")
        with pytest.raises(ParameterUploadCancelled) as caught:
            await task
        assert_failed_submission(caught.value, service)
        check_cancellation_redaction(caught.value)
        assert task.cancelled()
        assert storage.is_closed == (ownership == "owned")
        assert not target[0].c.is_closed
        assert not target[0].sync_client.is_closed
        assert not target[1].is_closed
        await assert_no_late_storage_requests(service, release)
        check_storage_constructor(constructor, ownership)
    finally:
        release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await storage.aclose()


async def assert_no_late_storage_requests(
    service: ParameterService, release: asyncio.Event
) -> None:
    requests = tuple(service.requests)
    release.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert tuple(service.requests) == requests
    assert [
        request.url.params.get("comp")
        for request in requests
        if request.url.host == "storage"
    ] == ["block", "block", "blocklist"]


def check_storage_constructor(constructor: Mock, ownership: str) -> None:
    if ownership == "owned":
        constructor.assert_called_once_with(follow_redirects=False, trust_env=False)
    else:
        constructor.assert_not_called()


def check_cancellation_redaction(error: ParameterUploadCancelled) -> None:
    assert isinstance(error.__cause__, asyncio.CancelledError)
    assert "fake-secret" in str(error.__cause__)
    assert "fake-secret" not in str(error)
    assert "fake-secret" not in error.failure.message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        (filename, size)
        for filename in ("file.txt", "file.txt.gz")
        for size in (1, 4194305)
    ],
)
async def test_helper_preserves_blob_media_metadata(
    *,
    target: tuple[AsyncClient, httpx.AsyncClient],
    tmp_path: Path,
    service: ParameterService,
    case: tuple[str, int],
) -> None:
    payload = media_source(tmp_path, filename=case[0], size=case[1])
    result = await upload_parameters_async(
        target[0], tmp_path, storage_client=target[1]
    )
    storage = [request for request in service.requests if request.url.host == "storage"]
    preparation = next(
        request
        for request in service.requests
        if "/binaryfilenode/" in request.url.path and request.method == "PUT"
    )
    check_media_headers(
        preparation, storage[-1], "gzip" if case[0].endswith(".gz") else None
    )
    assert service.content[1] == payload
    assert result.completed_trees == ("tree",)
    assert len(result.completed_files) == 1
    assert (
        result.completed_files[0].checksum
        == hashlib.md5(payload, usedforsecurity=False).hexdigest()
    )
    assert (
        storage[-1].headers["x-ms-blob-content-md5"]
        == base64.b64encode(bytes.fromhex(result.completed_files[0].checksum)).decode()
    )
    assert preparation.headers["checksum"] == result.completed_files[0].checksum
    assert [request.url.params.get("comp") for request in storage] == (
        [None] if case[1] == 1 else ["block", "block", "blocklist"]
    )
    for request in storage:
        assert request.url.query.startswith(b"sig=a%2Bb%2Fc&sv=1")
        assert request.headers["x-ms-version"] == "2021-12-02"
        assert int(request.headers["content-length"]) == len(request.content)
        assert not {
            "authorization",
            "project",
            "organizationguid",
            "cookie",
        }.intersection(request.headers)
