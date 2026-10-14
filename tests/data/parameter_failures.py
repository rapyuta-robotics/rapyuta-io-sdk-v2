# Copyright 2026 Rapyuta Robotics

"""Fault injection for upload integrity and storage completion tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from rapyuta_io_sdk_v2.helpers._parameter_source import read_chunk

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.exceptions import (
        ParameterUploadCancelled,
        ParameterUploadError,
    )
    from rapyuta_io_sdk_v2.helpers._parameter_source import SourceEntry
    from tests.data.parameter_data import ParameterService


def corrupt_chunk(entry: SourceEntry, offset: int) -> bytes:
    """Change a second-pass byte without changing length or filesystem metadata."""
    content = read_chunk(entry, offset)
    return b"!" + content[1:] if offset == 0 else content


def reject_blocklist(
    service: ParameterService, request: httpx.Request
) -> httpx.Response:
    """Accept every block and reject only the final storage commit."""
    if request.url.params.get("comp") == "blocklist":
        service.requests.append(request)
        return httpx.Response(500, text="block-list rejected")
    return service.storage(request)


def assert_failed_submission(
    error: ParameterUploadError | ParameterUploadCancelled, service: ParameterService
) -> None:
    """Require only previously acknowledged progress and no binary confirmation."""
    assert error.failure.path == "tree/b.bin"
    assert error.failure.stage == "transfer_blob"
    assert error.partial_result.completed_trees == ("alpha",)
    assert tuple(file.tree_path for file in error.partial_result.completed_files) == (
        "alpha/done.yaml",
        "tree/a.yaml",
    )
    assert error.partial_result.created_directories == ("alpha", "tree")
    assert error.partial_result.deleted_trees == ()
    assert all(request.method != "PATCH" for request in service.requests)
    assert "tree/c.bin" not in service.nodes
    assert service.content == {}
    assert service.blobs[1]["status"] == "Pending"
