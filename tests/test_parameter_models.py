# Copyright 2026 Rapyuta Robotics

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from rapyuta_io_sdk_v2 import (
    ParameterSkippedEntry,
    ParameterUploadOptions,
    ParameterUploadResult,
)
from rapyuta_io_sdk_v2.helpers._parameter_upload import UploadProgress
from rapyuta_io_sdk_v2.models.parameter import (
    ParameterBlobListResponse,
    ParameterCommitResponse,
    ParameterDeleteResponse,
    ParameterNodeDelete,
    ParameterNodeResponse,
    ParameterNodeWrite,
    ParameterTreeCreateResponse,
    ParameterTreeListResponse,
    ParameterUploadMetadata,
    ParameterUploadResponse,
)
from tests.data.parameter_data import (
    parameter_association,
    parameter_blob,
    parameter_node,
)

if TYPE_CHECKING:
    from pydantic import BaseModel


@pytest.mark.parametrize(
    "model",
    [
        ParameterTreeListResponse,
        ParameterTreeCreateResponse,
        ParameterNodeResponse,
        ParameterDeleteResponse,
        ParameterUploadResponse,
        ParameterCommitResponse,
        ParameterBlobListResponse,
    ],
)
@pytest.mark.parametrize("payload", [{}, {"data": None}, None])
def test_required_response_envelopes(model: type[BaseModel], payload: object) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_recursive_nodes_preserve_aliases_and_empty_text() -> None:
    payload = {
        "data": parameter_node(
            children=[
                parameter_node(
                    "tree/file.yaml", type="FileNode", data="", contentType="text/yaml"
                )
            ]
        )
    }
    node = ParameterNodeResponse.model_validate(payload)
    assert node.data.children[0].data == ""
    assert "blob_ref_id" not in node.data.children[0].model_fields_set
    assert (
        node.model_dump(mode="json", by_alias=True, exclude_unset=True)["data"][
            "children"
        ][0]["data"]
        == ""
    )


def test_blob_schema_and_associations() -> None:
    payload = {
        "data": {
            "isComplete": True,
            "blobRefs": [parameter_blob(association=[parameter_association()])],
        }
    }
    model = ParameterBlobListResponse.model_validate(payload)
    assert model.data.blob_refs[0].id == 1
    assert model.data.blob_refs[0].deleted_at is None
    assert model.data.blob_refs[0].association[0].sub_ref == "/file.bin"
    assert ParameterTreeListResponse(data=[]).data == []
    assert (
        ParameterBlobListResponse(
            data={"isComplete": True, "blobRefs": []}
        ).data.blob_refs
        == []
    )


@pytest.mark.parametrize(
    "values",
    [
        {"type": "FileNode"},
        {"type": "FileNode", "contentType": "text/plain"},
        {"type": "FileNode", "contentType": "text/yaml", "version": -1},
        {"type": "FileNode", "contentType": "text/yaml", "blobRefId": "0"},
        {
            "type": "FileNode",
            "contentType": "text/yaml",
            "blobRefId": "1",
            "data": "text",
        },
    ],
)
def test_invalid_node_write(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ParameterNodeWrite.model_validate(values)


def test_write_omission_and_delete_requirements() -> None:
    model = ParameterNodeWrite(node_type="FolderNode")
    assert model.model_dump(by_alias=True, exclude_unset=True) == {"type": "FolderNode"}
    assert (
        ParameterNodeWrite(node_type="FileNode", content_type="text/yaml", data="").data
        == ""
    )
    with pytest.raises(ValidationError):
        ParameterNodeDelete(node_type="FileNode", version=1)
    with pytest.raises(ValidationError):
        ParameterNodeDelete(node_type="FolderNode")


@pytest.mark.parametrize("checksum", ["A" * 32, "0" * 31, "xyz"])
def test_upload_checksum(checksum: str) -> None:
    with pytest.raises(ValidationError):
        ParameterUploadMetadata(checksum=checksum, content_type="text/plain")


@pytest.mark.parametrize(
    "values",
    [
        {"type": "FileNode"},
        {"type": "FolderNode", "blobRefId": "1"},
        {"type": "FileNode", "blobRefId": 1},
        {"type": "FileNode", "blobRefId": "0"},
    ],
)
def test_prepared_upload_requires_file_and_decimal_id(
    values: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ParameterUploadResponse(data=parameter_node(**values))


def test_exact_acknowledgments() -> None:
    with pytest.raises(ValidationError):
        ParameterCommitResponse(data={"upload": False})
    with pytest.raises(ValidationError):
        ParameterDeleteResponse(data="done")


@pytest.mark.parametrize(
    "values",
    [{"tree_names": "alpha"}, {"as_folder": "false"}, {"delete_existing_trees": 1}],
)
def test_strict_helper_options(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ParameterUploadOptions.model_validate(values)


def test_results_are_deeply_immutable() -> None:
    result = ParameterUploadResult(
        skipped_entries=(ParameterSkippedEntry(path="link", reason="symbolic_link"),)
    )
    with pytest.raises(ValidationError):
        result.selected_trees = ("changed",)
    with pytest.raises(ValidationError):
        result.skipped_entries[0].path = "changed"


@pytest.mark.parametrize("value", [1, "true", None, False])
def test_commit_requires_boolean_true(value: object) -> None:
    with pytest.raises(ValidationError):
        ParameterCommitResponse(data={"upload": value})


@pytest.mark.parametrize("scheme", ["https", "HTTPS", "HtTpS", "HTTP"])
@pytest.mark.parametrize("cancelled", [False, True])
def test_public_failure_redacts_all_http_scheme_cases(
    *, scheme: str, cancelled: bool
) -> None:
    message = f"Cannot sign {scheme}://storage/blob?sig=fake-secret&sp=w"
    progress = UploadProgress(path="tree/file.bin")
    error = (
        progress.cancelled(asyncio.CancelledError(message))
        if cancelled
        else progress.error(ValueError(message))
    )
    assert "fake-secret" not in error.failure.message
    assert "fake-secret" not in str(error)
    assert f"{scheme}://storage/blob?<redacted>" in error.failure.message
