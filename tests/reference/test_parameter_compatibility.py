# Copyright 2026 Rapyuta Robotics

from __future__ import annotations

import asyncio
import io
import json
from typing import TYPE_CHECKING

import httpx
import pytest
import rapyuta_io
import requests

from rapyuta_io_sdk_v2 import AsyncClient, Client, Configuration, ParameterUploadOptions
from rapyuta_io_sdk_v2.helpers import upload_parameters, upload_parameters_async
from tests.data.parameter_data import ParameterService
from tests.helpers.conftest import mixed_source

if TYPE_CHECKING:
    from pathlib import Path

    from rapyuta_io_sdk_v2 import ParameterUploadResult


REFERENCE_FILES = 100


def legacy_response(service: ParameterService, **kwargs: object) -> requests.Response:
    """Serve the actual downloader solely from captured helper-produced state."""
    url = httpx.URL(kwargs["url"])
    assert kwargs["method"] == "GET"
    response = requests.Response()
    response.status_code = 200
    response.url = str(url)
    if url.host == "storage":
        content = service.content[int(url.path.lstrip("/"))]
        response.raw = io.BytesIO(content)
        return response
    assert url.host == "core"
    request = httpx.Request("GET", url, params=kwargs.get("params"))
    response.raw = io.BytesIO(service.platform(request).content)
    return response


async def submit_async(
    service: ParameterService, source: Path, options: ParameterUploadOptions
) -> ParameterUploadResult:
    client = AsyncClient(
        Configuration(
            auth_token="token", project_guid="project", core_api_host="https://core"
        )
    )
    await client.c.aclose()
    client.c = httpx.AsyncClient(transport=httpx.MockTransport(service.platform))
    try:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(service.storage)
        ) as storage:
            return await upload_parameters_async(
                client, source, options=options, storage_client=storage
            )
    finally:
        await client.c.aclose()
        client.sync_client.close()


def submit(
    service: ParameterService, source: Path, options: ParameterUploadOptions
) -> ParameterUploadResult:
    client = Client(
        Configuration(
            auth_token="token", project_guid="project", core_api_host="https://core"
        )
    )
    client.c.close()
    client.c = httpx.Client(transport=httpx.MockTransport(service.platform))
    try:
        with httpx.Client(transport=httpx.MockTransport(service.storage)) as storage:
            return upload_parameters(
                client, source, options=options, storage_client=storage
            )
    finally:
        client.c.close()


def add_boundary_files(source: Path) -> None:
    tree = source / "alpha"
    (tree / "zero.bin").write_bytes(b"")
    (tree / "large.bin").write_bytes(b"x" * 4194305)
    (tree / "escaped.json").write_text('"' + "é" * 22000 + '"', encoding="utf-8")
    (tree / "rawlarge.yaml").write_bytes(b"invalid[" + b"x" * 131072)
    (tree / "inline.json").write_bytes(b'{"key": "value"}\r\n')
    overhead = (
        len(
            json.dumps(
                {"type": "FileNode", "data": "", "contentType": "application/json"}
            )
        )
        + 200
    )
    # Original JSON quotes each occupy two characters in the stored estimate.
    text = '"' + "a" * (131072 - overhead - 4) + '"'
    (tree / "atlimit.json").write_text(text, encoding="utf-8")
    (tree / "overlimit.json").write_text(text[:-1] + 'a"', encoding="utf-8")
    (tree / "rawexact.json").write_text('"' + "b" * 131070 + '"', encoding="utf-8")


def compare_restored(
    source: Path, restored: Path, result: ParameterUploadResult
) -> None:
    for file in result.completed_files:
        assert (restored / file.tree_path).read_bytes() == (
            source / file.tree_path
        ).read_bytes()
    for directory in result.created_directories:
        assert (restored / directory).is_dir()
    actual = {
        str(path.relative_to(restored))
        for path in restored.rglob("*")
        if path.is_file()
    }
    assert actual == {file.tree_path for file in result.completed_files}


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("selected", [(), ("alpha",)])
def test_actual_v1_downloader_round_trip(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    selected: tuple[str, ...],
) -> None:
    source = mixed_source(tmp_path / "source")
    add_boundary_files(source)
    service = ParameterService()
    options = ParameterUploadOptions(tree_names=selected)
    result = (
        submit(service, source, options)
        if mode == "sync"
        else asyncio.run(submit_async(service, source, options))
    )
    routes = {
        file.tree_path.rsplit("/", 1)[1]: file.storage
        for file in result.completed_files
    }
    assert routes["atlimit.json"] == "inline"
    assert routes["overlimit.json"] == "blob"
    assert routes["rawexact.json"] == "blob"
    monkeypatch.setattr(
        requests, "request", lambda **kwargs: legacy_response(service, **kwargs)
    )

    def reject_network(*_args: object, **_kwargs: object) -> None:
        message = "Unhandled reference network request"
        raise AssertionError(message)

    monkeypatch.setattr(requests.sessions.Session, "request", reject_network)
    consumer = rapyuta_io.Client(auth_token="token", project="project")
    # SDK v1 has no public constructor endpoint override.
    monkeypatch.setattr(consumer._paramserver_client, "_core_api_host", "https://core")  # noqa: SLF001
    restored = tmp_path / "restored"
    consumer.download_configurations(
        str(restored), tree_names=list(result.selected_trees)
    )
    compare_restored(source, restored, result)


def legacy_source(root: Path) -> Path:
    source = mixed_source(root)
    for name in ("alpha", "beta"):
        tree = source / name
        (tree / "empty").rename(tree / "one" / "empty")
        parent = tree / "one" / "two" / "three" / "four"
        for file in (parent / "five").iterdir():
            file.rename(parent / file.name)
        (tree / "one" / "skip.bin").write_bytes(b"legacy skip")
    return source


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_actual_v1_legacy_and_recreation(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    source = legacy_source(tmp_path / "source")
    add_boundary_files(source)
    service = ParameterService()
    options = ParameterUploadOptions(as_folder=False)
    invoke = (
        submit if mode == "sync" else lambda *args: asyncio.run(submit_async(*args))
    )
    result = invoke(service, source, options)
    assert len(result.completed_files) >= REFERENCE_FILES
    options = ParameterUploadOptions(
        as_folder=False, tree_names=("alpha",), delete_existing_trees=True
    )
    result = invoke(service, source, options)
    assert result.deleted_trees == ("alpha",)
    monkeypatch.setattr(
        requests, "request", lambda **kwargs: legacy_response(service, **kwargs)
    )

    def reject_network(*_args: object, **_kwargs: object) -> None:
        message = "Unhandled reference network request"
        raise AssertionError(message)

    monkeypatch.setattr(requests.sessions.Session, "request", reject_network)
    consumer = rapyuta_io.Client(auth_token="token", project="project")
    # SDK v1 has no public constructor endpoint override.
    monkeypatch.setattr(consumer._paramserver_client, "_core_api_host", "https://core")  # noqa: SLF001
    restored = tmp_path / "restored"
    consumer.download_configurations(
        str(restored), tree_names=list(result.selected_trees)
    )
    compare_restored(source, restored, result)
