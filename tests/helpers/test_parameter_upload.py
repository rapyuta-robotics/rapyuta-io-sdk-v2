# Copyright 2026 Rapyuta Robotics

from __future__ import annotations

import base64
import hashlib
import os
from functools import partial
from http import HTTPStatus
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import httpx
import pytest

from rapyuta_io_sdk_v2 import Client, Configuration, ParameterUploadOptions
from rapyuta_io_sdk_v2.exceptions import ParameterUploadError
from rapyuta_io_sdk_v2.helpers import _parameter_storage as storage_module
from rapyuta_io_sdk_v2.helpers import parameter as helper_module
from rapyuta_io_sdk_v2.helpers import upload_parameters
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
    from collections.abc import Iterator
    from pathlib import Path

    from tests.data.parameter_data import ParameterService


DUPLICATE_ERROR = "blobRef signed url not generated or blobRef already uploaded"
LEGACY_FILES = 2
TOTAL_FILES = 100
FILES_PER_TREE = 50
UNIQUE_BLOBS = 25
LINK_COUNT = 2


@pytest.fixture
def target(service: ParameterService) -> Iterator[tuple[Client, httpx.Client]]:
    instance = Client(
        Configuration(
            auth_token="token", project_guid="project", core_api_host="https://core"
        )
    )
    instance.c.close()
    instance.c = httpx.Client(transport=httpx.MockTransport(service.platform))
    storage = httpx.Client(transport=httpx.MockTransport(service.storage))
    yield instance, storage
    instance.c.close()
    storage.close()


def test_upload_mixed_source(
    *, target: tuple[Client, httpx.Client], source: Path, service: ParameterService
) -> None:
    client, storage = target
    result = upload_parameters(client, source, storage_client=storage)
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


@pytest.mark.parametrize(
    "names", [("alpha",), ("alpha", "missing"), ("alpha", "alpha")]
)
def test_exact_selection(
    *, target: tuple[Client, httpx.Client], source: Path, names: tuple[str, ...]
) -> None:
    client, storage = target
    result = upload_parameters(
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


def test_no_matches_fail_before_mutation(
    *, target: tuple[Client, httpx.Client], source: Path, service: ParameterService
) -> None:
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(
            client,
            source,
            options=ParameterUploadOptions(tree_names=("missing",)),
            storage_client=storage,
        )
    assert caught.value.failure.stage == "validate_source"
    assert service.requests == []


def test_empty_source_noop(
    *, target: tuple[Client, httpx.Client], tmp_path: Path
) -> None:
    client, storage = target
    (tmp_path / "loose").write_bytes(b"ignored")
    result = upload_parameters(client, tmp_path, storage_client=storage)
    assert result.selected_trees == ()
    assert result.completed_trees == ()
    assert result.skipped_entries[0].path == "loose"


@pytest.mark.parametrize("filename", ["bad name.txt", ".hidden", "a" * 51])
def test_preflight_rejects_backend_names(
    *,
    target: tuple[Client, httpx.Client],
    source: Path,
    service: ParameterService,
    filename: str,
) -> None:
    (source / "alpha" / filename).write_bytes(b"data")
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(client, source, storage_client=storage)
    assert caught.value.failure.stage == "validate_source"
    assert service.requests == []


def test_links_are_skipped(
    *, target: tuple[Client, httpx.Client], source: Path
) -> None:
    (source / "linked").symlink_to(source / "alpha", target_is_directory=True)
    (source / "alpha" / "link.bin").symlink_to(source / "loose.txt")
    client, storage = target
    result = upload_parameters(client, source, storage_client=storage)
    assert (
        sum(entry.reason == "symbolic_link" for entry in result.skipped_entries)
        == LINK_COUNT
    )
    assert len(result.completed_files) == TOTAL_FILES


def test_transfer_failure_exposes_progress(
    *, target: tuple[Client, httpx.Client], source: Path, service: ParameterService
) -> None:
    client, storage = target
    service.reject = ("PATCH", "/api/paramserver/binaryfilenode/alpha/blobref/1", 500)
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(client, source, storage_client=storage)
    error = caught.value
    assert error.failure.stage == "confirm_upload"
    assert error.failure.path.endswith("file0.bin")
    assert error.partial_result.created_directories
    assert error.partial_result.completed_files == ()
    assert error.partial_result.completed_trees == ()
    assert error.__cause__ is not None


@pytest.mark.parametrize(
    "headers", [{"Authorization": "secret"}, {"project": "project"}]
)
def test_unsafe_storage_rejected(
    *,
    target: tuple[Client, httpx.Client],
    source: Path,
    service: ParameterService,
    headers: dict[str, str],
) -> None:
    client, storage = target
    storage.headers.update(headers)
    with pytest.raises(ParameterUploadError):
        upload_parameters(client, source, storage_client=storage)
    assert service.requests == []


@pytest.mark.parametrize(
    "payload", [b"[not a mapping]", b"key: [" + "é".encode() * 22000]
)
def test_invalid_candidates_validate_before_size(
    *, target: tuple[Client, httpx.Client], tmp_path: Path, payload: bytes
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "file.yaml").write_bytes(payload)
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(client, tmp_path, storage_client=storage)
    assert caught.value.failure.stage == "read_file"
    assert caught.value.partial_result.completed_files == ()


def test_large_invalid_structured_file_uses_blob(
    *, target: tuple[Client, httpx.Client], tmp_path: Path, service: ParameterService
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    payload = b"[invalid" + b"x" * 131072
    (tree / "file.yaml").write_bytes(payload)
    client, storage = target
    result = upload_parameters(client, tmp_path, storage_client=storage)
    assert result.completed_files[0].storage == "blob"
    assert service.content[1] == payload


@pytest.mark.parametrize(
    "case",
    [
        ("/tree/alpha", "create_tree"),
        ("/tree/alpha/empty", "create_node"),
        ("/binaryfilenode/alpha/one/two/three/four/five/file0.bin", "prepare_upload"),
    ],
)
def test_platform_failure_stage(
    *,
    target: tuple[Client, httpx.Client],
    source: Path,
    service: ParameterService,
    case: tuple[str, str],
) -> None:
    path, stage = case
    service.reject = ("PUT", "/api/paramserver" + path, 500)
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(client, source, storage_client=storage)
    assert caught.value.failure.stage == stage
    assert caught.value.partial_result.completed_trees == ()
    assert "beta" not in service.nodes


def test_storage_failure_never_confirms(
    *, target: tuple[Client, httpx.Client], source: Path, service: ParameterService
) -> None:
    client, storage = target
    storage.close()
    storage = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500)))
    try:
        with pytest.raises(ParameterUploadError) as caught:
            upload_parameters(client, source, storage_client=storage)
        assert caught.value.failure.stage == "transfer_blob"
        assert caught.value.partial_result.completed_files == ()
        assert all(request.method != "PATCH" for request in service.requests)
        assert "a%2Bb" not in str(caught.value)
    finally:
        storage.close()


@pytest.mark.parametrize("uploaded", [False, True])
def test_url_less_prepare_requires_uploaded_reference(
    *,
    target: tuple[Client, httpx.Client],
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

    client.c.close()
    client.c = httpx.Client(transport=httpx.MockTransport(platform))
    if uploaded:
        result = upload_parameters(client, tmp_path, storage_client=storage)
        assert len(result.completed_files) == 1
    else:
        with pytest.raises(ParameterUploadError) as caught:
            upload_parameters(client, tmp_path, storage_client=storage)
        assert caught.value.failure.stage == "verify_blob"
    assert not any(request.url.host == "storage" for request in service.requests)


@pytest.mark.parametrize("case", [(403, True), (403, False), (400, True)])
def test_ambiguous_commit_verifies_status(
    *,
    target: tuple[Client, httpx.Client],
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

    client.c.close()
    client.c = httpx.Client(transport=httpx.MockTransport(platform))
    if status == HTTPStatus.FORBIDDEN and uploaded:
        result = upload_parameters(client, tmp_path, storage_client=storage)
        assert len(result.completed_files) == 1
    else:
        with pytest.raises(ParameterUploadError) as caught:
            upload_parameters(client, tmp_path, storage_client=storage)
        assert caught.value.failure.stage == "confirm_upload"
        assert caught.value.partial_result.completed_files == ()
        assert str(caught.value.__cause__) == DUPLICATE_ERROR


def test_changed_source_after_preparation_never_confirms(
    *, target: tuple[Client, httpx.Client], tmp_path: Path, service: ParameterService
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

    client.c.close()
    client.c = httpx.Client(transport=httpx.MockTransport(platform))
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(client, tmp_path, storage_client=storage)
    assert caught.value.failure.stage == "transfer_blob"
    assert all(request.method != "PATCH" for request in service.requests)


def test_recreation_only_replaces_selected_tree(
    *, target: tuple[Client, httpx.Client], source: Path, service: ParameterService
) -> None:
    client, storage = target
    upload_parameters(client, source, storage_client=storage)
    service.nodes["alpha/remote.bin"] = {"type": "FileNode"}
    service.nodes["beta/remote.bin"] = {"type": "FileNode"}
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(client, source, storage_client=storage)
    assert caught.value.failure.stage == "create_tree"
    assert "alpha/remote.bin" in service.nodes
    options = ParameterUploadOptions(tree_names=("alpha",), delete_existing_trees=True)
    result = upload_parameters(client, source, options=options, storage_client=storage)
    assert result.deleted_trees == ("alpha",)
    assert "alpha/remote.bin" not in service.nodes
    assert "beta/remote.bin" in service.nodes
    assert result.completed_trees == ("alpha",)


@pytest.mark.parametrize("stage", ["delete_tree", "create_tree"])
def test_recreation_failure_preserves_deletions(
    *,
    target: tuple[Client, httpx.Client],
    source: Path,
    service: ParameterService,
    stage: str,
) -> None:
    verb = "DELETE" if stage == "delete_tree" else "PUT"
    service.reject = (verb, "/api/paramserver/tree/alpha", 500)
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(
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


def test_legacy_hierarchy_and_attribute_file_skips(
    *, target: tuple[Client, httpx.Client], tmp_path: Path, service: ParameterService
) -> None:
    tree = tmp_path / "tree"
    parent = tree / "attribute" / "value" / "second" / "value"
    parent.mkdir(parents=True)
    (tree / "attribute" / "skip.bin").write_bytes(b"skip")
    (tree / "file.yaml").write_bytes(b"key: value\r\n")
    large = b"[invalid" + b"x" * 131072
    (parent / "large.json").write_bytes(large)
    client, storage = target
    result = upload_parameters(
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


def test_known_legacy_restriction_fails_preflight(
    *, target: tuple[Client, httpx.Client], tmp_path: Path, service: ParameterService
) -> None:
    (tmp_path / "tree" / "one").mkdir(parents=True)
    (tmp_path / "tree" / "two").mkdir()
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(
            client,
            tmp_path,
            options=ParameterUploadOptions(as_folder=False),
            storage_client=storage,
        )
    assert caught.value.failure.stage == "validate_source"
    assert service.requests == []


def test_invalid_tree_has_specific_failure_path(
    *, target: tuple[Client, httpx.Client], tmp_path: Path, service: ParameterService
) -> None:
    (tmp_path / "bad name").mkdir()
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(client, tmp_path, storage_client=storage)
    assert caught.value.failure.path == "bad name"
    assert caught.value.failure.stage == "validate_source"
    assert service.requests == []


@pytest.mark.parametrize("setting", ["cookies", "auth", "redirects", "closed"])
def test_storage_configuration_rejected_before_mutation(
    *,
    target: tuple[Client, httpx.Client],
    source: Path,
    service: ParameterService,
    setting: str,
) -> None:
    client, storage = target
    if setting == "cookies":
        storage.cookies.set("session", "secret")
    elif setting == "auth":
        storage.auth = ("user", "password")
    elif setting == "redirects":
        storage.follow_redirects = True
    else:
        storage.close()
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(client, source, storage_client=storage)
    assert caught.value.failure.stage == "validate_source"
    assert service.requests == []


@pytest.mark.parametrize("field", ["auth_token", "project_guid", "core_api_host"])
def test_platform_configuration_rejected_before_mutation(
    *,
    target: tuple[Client, httpx.Client],
    source: Path,
    service: ParameterService,
    field: str,
) -> None:
    client, storage = target
    if field == "core_api_host":
        client.config.hosts[field] = None
    else:
        setattr(client.config, field, None)
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(client, source, storage_client=storage)
    assert caught.value.failure.stage == "validate_source"
    assert service.requests == []


@pytest.mark.skipif(
    not hasattr(os, "mkfifo"), reason="FIFO requires a POSIX filesystem"
)
def test_special_entries_are_not_opened(
    *, target: tuple[Client, httpx.Client], source: Path
) -> None:
    os.mkfifo(source / "alpha" / "pipe")
    client, storage = target
    result = upload_parameters(client, source, storage_client=storage)
    assert any(
        entry.path == "alpha/pipe" and entry.reason == "special_entry"
        for entry in result.skipped_entries
    )


@pytest.mark.parametrize(
    "relative", ["attribute/value/attribute", "attribute/value.ext"]
)
def test_invalid_legacy_path_fails_before_recreation(
    *,
    target: tuple[Client, httpx.Client],
    tmp_path: Path,
    service: ParameterService,
    relative: str,
) -> None:
    (tmp_path / "tree" / relative).mkdir(parents=True)
    client, storage = target
    options = ParameterUploadOptions(as_folder=False, delete_existing_trees=True)
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(client, tmp_path, options=options, storage_client=storage)
    assert caught.value.failure.path == "tree/" + relative
    assert caught.value.failure.stage == "validate_source"
    assert service.requests == []


def test_folder_path_is_validated_with_trailing_slash(
    *, target: tuple[Client, httpx.Client], tmp_path: Path, service: ParameterService
) -> None:
    name = "a" * 50 + ".extension"
    (tmp_path / "tree" / name).mkdir(parents=True)
    client, storage = target
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(client, tmp_path, storage_client=storage)
    assert caught.value.failure.stage == "validate_source"
    assert service.requests == []


@pytest.mark.parametrize(
    "case",
    [
        (operation, error_type)
        for operation in ("lstat", "open")
        for error_type in (FileNotFoundError, PermissionError)
    ],
)
def test_preflight_os_error_identifies_child(
    *,
    target: tuple[Client, httpx.Client],
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
        upload_parameters(
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


@pytest.mark.parametrize("scheme", ["HTTPS", "HtTpS"])
@pytest.mark.parametrize("scenario", ["platform", "malformed", "verification"])
def test_failure_redacts_signed_query(
    *,
    target: tuple[Client, httpx.Client],
    tmp_path: Path,
    service: ParameterService,
    scheme: str,
    scenario: str,
) -> None:
    (tmp_path / "tree").mkdir()
    (tmp_path / "tree/file.bin").write_bytes(b"binary")
    client, storage = target
    platform = partial(signed_query_error, service, scenario=scenario, scheme=scheme)

    client.c.close()
    client.c = httpx.Client(transport=httpx.MockTransport(platform))
    with pytest.raises(ParameterUploadError) as caught:
        upload_parameters(client, tmp_path, storage_client=storage)
    assert "fake-secret" not in caught.value.failure.message
    assert "fake-secret" not in str(caught.value)
    if scenario == "verification":
        assert "fake-secret" not in str(caught.value.__cause__.__notes__)
        assert "fake-secret" in str(caught.value.__cause__.__cause__)
    else:
        assert "fake-secret" in str(caught.value.__cause__)
        assert all(request.method != "PATCH" for request in service.requests)
    assert caught.value.partial_result.completed_files == ()


@pytest.mark.parametrize(
    "case",
    [
        (failure, ownership)
        for failure in ("corruption", "blocklist")
        for ownership in ("owned", "injected")
    ],
)
def test_storage_failure_preserves_progress_and_ownership(
    *,
    target: tuple[Client, httpx.Client],
    failure_source: Path,
    service: ParameterService,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[str, str],
) -> None:
    failure, ownership = case
    if failure == "corruption":
        monkeypatch.setattr(storage_module, "read_chunk", corrupt_chunk)
    storage = httpx.Client(
        transport=httpx.MockTransport(partial(reject_blocklist, service)),
        follow_redirects=False,
        trust_env=False,
    )
    constructor = Mock(return_value=storage)
    monkeypatch.setattr(helper_module, "httpx", SimpleNamespace(Client=constructor))
    try:
        with pytest.raises(ParameterUploadError) as caught:
            upload_parameters(
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
        storage.close()


@pytest.mark.parametrize(
    "case",
    [
        (filename, size)
        for filename in ("file.txt", "file.txt.gz")
        for size in (1, 4194305)
    ],
)
def test_helper_preserves_blob_media_metadata(
    *,
    target: tuple[Client, httpx.Client],
    tmp_path: Path,
    service: ParameterService,
    case: tuple[str, int],
) -> None:
    payload = media_source(tmp_path, filename=case[0], size=case[1])
    result = upload_parameters(target[0], tmp_path, storage_client=target[1])
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
