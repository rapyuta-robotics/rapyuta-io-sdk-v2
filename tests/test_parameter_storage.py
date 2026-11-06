# Copyright 2026 Rapyuta Robotics

from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING
from urllib.parse import parse_qs
from xml.etree import ElementTree as ET

import httpx
import pytest

from rapyuta_io_sdk_v2 import Configuration, ParameterUploadOptions
from rapyuta_io_sdk_v2.helpers import _parameter_storage as storage_module
from rapyuta_io_sdk_v2.helpers._parameter_source import (
    BLOCK_SIZE,
    MAX_BLOB_SIZE,
    SourceError,
    classify_file,
    preflight,
    read_chunk,
)
from rapyuta_io_sdk_v2.helpers._parameter_storage import (
    transfer_blob,
    transfer_blob_async,
)
from tests.data.parameter_data import media_source
from tests.data.parameter_failures import corrupt_chunk

if TYPE_CHECKING:
    from pathlib import Path

    from rapyuta_io_sdk_v2.helpers._parameter_source import ClassifiedFile


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("size", [0, 1, 4194304, 4194305, 8388617])
async def test_blob_transfer_protocol(*, tmp_path: Path, mode: str, size: int) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    payload = b"z" * size
    (tree / "file.bin").write_bytes(payload)
    manifest = preflight(
        Configuration(auth_token="token", project_guid="project"),
        tmp_path,
        ParameterUploadOptions(),
    )
    source = classify_file(manifest.entries[0])
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201)

    transport = httpx.MockTransport(respond)
    url = "https://storage/blob?sig=a%2Bb%2Fc&sp=w"
    if mode == "sync":
        with httpx.Client(transport=transport) as client:
            transfer_blob(client, url, source)
    else:
        async with httpx.AsyncClient(transport=transport) as client:
            await transfer_blob_async(client, url, source)
    check_transfers(requests, payload)


def check_transfers(requests: list[httpx.Request], payload: bytes) -> None:
    for request in requests:
        assert request.url.query.startswith(b"sig=a%2Bb%2Fc&sp=w")
        assert request.headers["x-ms-version"] == "2021-12-02"
        assert int(request.headers["content-length"]) == len(request.content)
        assert "authorization" not in request.headers
    expected = base64.b64encode(
        hashlib.md5(payload, usedforsecurity=False).digest()
    ).decode()
    assert requests[-1].headers["x-ms-blob-content-md5"] == expected
    if len(requests) == 1:
        assert requests[0].headers["x-ms-blob-type"] == "BlockBlob"
        assert requests[0].content == payload
    else:
        check_blocks(requests, payload)


def check_blocks(requests: list[httpx.Request], payload: bytes) -> None:
    ids = [
        parse_qs(request.url.query.decode())["blockid"][0] for request in requests[:-1]
    ]
    assert len(set(ids)) == len(ids)
    assert len({len(identifier) for identifier in ids}) == 1
    assert b"".join(request.content for request in requests[:-1]) == payload
    # XML is generated locally by the isolated adapter, never a remote input.
    root = ET.fromstring(requests[-1].content)  # noqa: S314
    assert [node.text for node in root] == ids
    assert "content-md5" not in requests[-1].headers
    for request in requests[:-1]:
        assert len(request.content) <= BLOCK_SIZE
        checksum = hashlib.md5(request.content, usedforsecurity=False).digest()
        assert request.headers["content-md5"] == base64.b64encode(checksum).decode()


@pytest.mark.parametrize("delta", [0, 1])
def test_maximum_size_preflight(tmp_path: Path, delta: int) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    with (tree / "file.bin").open("wb") as stream:
        stream.truncate(MAX_BLOB_SIZE + delta)
    config = Configuration(auth_token="token", project_guid="project")
    if delta:
        with pytest.raises(SourceError, match=str(MAX_BLOB_SIZE)):
            preflight(config, tmp_path, ParameterUploadOptions())
    else:
        manifest = preflight(config, tmp_path, ParameterUploadOptions())
        assert manifest.entries[0].identity.st_size == MAX_BLOB_SIZE


def test_changed_ancestor_is_not_followed(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "file.bin").write_bytes(b"original")
    config = Configuration(auth_token="token", project_guid="project")
    entry = preflight(config, tmp_path, ParameterUploadOptions()).entries[0]
    tree.rename(tmp_path / "moved")
    tree.symlink_to(tmp_path / "moved", target_is_directory=True)
    with pytest.raises(SourceError, match="ancestor changed"):
        read_chunk(entry, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_changed_transfer_never_commits_blocks(tmp_path: Path, mode: str) -> None:
    # An injected source mutation after the first accepted block must be detected.
    tree = tmp_path / "tree"
    tree.mkdir()
    path = tree / "file.bin"
    path.write_bytes(b"z" * (BLOCK_SIZE + 1))
    config = Configuration(auth_token="token", project_guid="project")
    source = classify_file(
        preflight(config, tmp_path, ParameterUploadOptions()).entries[0]
    )
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path.write_bytes(b"changed")
        return httpx.Response(201)

    transport = httpx.MockTransport(respond)

    async def transfer() -> None:
        if mode == "sync":
            with httpx.Client(transport=transport) as client:
                transfer_blob(client, "https://storage/blob?sig=secret", source)
        else:
            async with httpx.AsyncClient(transport=transport) as client:
                await transfer_blob_async(
                    client, "https://storage/blob?sig=secret", source
                )

    with pytest.raises(ValueError, match="changed"):
        await transfer()
    assert len(requests) == 1
    assert b"comp=blocklist" not in requests[0].url.query


@pytest.fixture
def classified_source(tmp_path: Path) -> ClassifiedFile:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "file.bin").write_bytes(b"z" * (BLOCK_SIZE + 1))
    config = Configuration(auth_token="token", project_guid="project")
    return classify_file(
        preflight(config, tmp_path, ParameterUploadOptions()).entries[0]
    )


async def run_transfer(
    mode: str,
    transport: httpx.MockTransport,
    source: ClassifiedFile,
    *,
    url: str = "https://storage/blob?sig=secret",
) -> None:
    if mode == "sync":
        with httpx.Client(transport=transport) as client:
            transfer_blob(client, url, source)
    else:
        async with httpx.AsyncClient(transport=transport) as client:
            await transfer_blob_async(client, url, source)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("failure", ["corruption", "blocklist"])
async def test_transfer_failure_does_not_finalize(
    *,
    classified_source: ClassifiedFile,
    mode: str,
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        status = 500 if request.url.params.get("comp") == "blocklist" else 201
        return httpx.Response(status)

    if failure == "corruption":
        monkeypatch.setattr(storage_module, "read_chunk", corrupt_chunk)
    error = ValueError if failure == "corruption" else httpx.HTTPStatusError
    message = "checksum changed" if failure == "corruption" else "status 500"
    with pytest.raises(error, match=message):
        await run_transfer(mode, httpx.MockTransport(respond), classified_source)
    # Reading may update access time; content and identity metadata stay fixed.
    actual = classified_source.entry.path.lstat()
    original = classified_source.entry.identity
    assert actual.st_size == original.st_size
    assert (actual.st_mtime_ns, actual.st_ctime_ns) == (
        original.st_mtime_ns,
        original.st_ctime_ns,
    )
    assert (actual.st_dev, actual.st_ino, actual.st_mode) == (
        original.st_dev,
        original.st_ino,
        original.st_mode,
    )
    assert sum(len(request.content) for request in requests[:2]) == BLOCK_SIZE + 1
    assert [request.url.params.get("comp") for request in requests] == (
        ["block", "block"]
        if failure == "corruption"
        else ["block", "block", "blocklist"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("size", [1, BLOCK_SIZE + 1])
@pytest.mark.parametrize("filename", ["file.txt", "file.txt.gz"])
async def test_storage_media_properties(
    *, tmp_path: Path, mode: str, size: int, filename: str
) -> None:
    payload = media_source(tmp_path, filename=filename, size=size)
    config = Configuration(auth_token="token", project_guid="project")
    source = classify_file(
        preflight(config, tmp_path, ParameterUploadOptions()).entries[0]
    )
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201)

    await run_transfer(
        mode,
        httpx.MockTransport(respond),
        source,
        url="https://storage/blob?sig=a%2Bb%2Fc&sp=w",
    )
    check_transfers(requests, payload)
    assert requests[-1].headers["x-ms-blob-content-type"] == "text/plain"
    assert requests[-1].headers.get("x-ms-blob-content-encoding") == (
        "gzip" if filename.endswith(".gz") else None
    )
    if len(requests) > 1:
        assert requests[-1].url.params["comp"] == "blocklist"
        assert requests[-1].headers["content-type"] == "application/xml"
