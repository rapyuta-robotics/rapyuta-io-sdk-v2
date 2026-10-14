# Copyright 2026 Rapyuta Robotics

"""Typed wire contracts for v1 Parameter operations and directory uploads."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from rapyuta_io_sdk_v2.models.base import SDKModel

BlobID = Annotated[str, Field(pattern=r"^[1-9][0-9]*$", strict=True)]
Checksum = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
MediaType = Annotated[str, Field(pattern=r"^[-\w.]+/[-+\w.]+$")]
Version = Annotated[int, Field(ge=0, strict=True)]
PositiveID = Annotated[int, Field(gt=0, strict=True)]


class ParameterNodeType(StrEnum):
    """Node kinds accepted by the Parameter service."""

    VALUE = "ValueNode"
    ATTRIBUTE = "AttributeNode"
    FOLDER = "FolderNode"
    FILE = "FileNode"


class ParameterNode(SDKModel):
    """A recursive server node with optimistic version and server metadata."""

    node_type: ParameterNodeType = Field(alias="type")
    version: Version
    name: str
    path: str
    updated_at: datetime = Field(alias="updatedAt")
    user_guid: str = Field(alias="userGUID")
    children: list[ParameterNode] = Field(default_factory=list)
    data: str | None = None
    content_type: str | None = Field(default=None, alias="contentType")
    blob_ref_id: BlobID | None = Field(default=None, alias="blobRefId")
    checksum: str | None = None
    upload_url: str | None = Field(default=None, alias="uploadUrl")


class ParameterNodeWrite(SDKModel):
    """One child write; version zero creates, an existing version updates."""

    node_type: ParameterNodeType = Field(alias="type")
    version: Version = 0
    data: str | None = None
    content_type: MediaType | None = Field(default=None, alias="contentType")
    blob_ref_id: BlobID | None = Field(default=None, alias="blobRefId")
    checksum: str | None = None
    upload_url: str | None = Field(default=None, alias="uploadUrl")

    @model_validator(mode="after")
    def validate_file(self) -> Self:
        """Require media metadata and distinguish inline content from references."""
        if self.data and self.blob_ref_id:
            message = "data and blob_ref_id are mutually exclusive"
            raise ValueError(message)
        if self.node_type == ParameterNodeType.FILE:
            self._validate_file_content()
        return self

    def _validate_file_content(self) -> None:
        if not self.content_type:
            message = "FileNode requires content_type"
            raise ValueError(message)
        if not self.blob_ref_id and self.content_type not in {
            "application/json",
            "text/yaml",
        }:
            message = "Binary FileNode requires blob_ref_id"
            raise ValueError(message)


class ParameterNodeDelete(SDKModel):
    """Version and node kind required to delete one child."""

    version: Version
    node_type: ParameterNodeType = Field(alias="type")
    content_type: MediaType | None = Field(default=None, alias="contentType")

    @model_validator(mode="after")
    def validate_file(self) -> Self:
        """Require the media type when deleting a file node."""
        if self.node_type == ParameterNodeType.FILE and not self.content_type:
            message = "FileNode deletion requires content_type"
            raise ValueError(message)
        return self


class ParameterTreeQuery(SDKModel):
    """Optional repeated regular-expression filters for remote tree names."""

    instances: tuple[str, ...] = ()


class ParameterBlobQuery(SDKModel):
    """Nonempty repeated tree names for a blob-reference listing."""

    tree_names: tuple[str, ...] = Field(alias="treeNames", min_length=1)


class ParameterUploadMetadata(SDKModel):
    """Headers for a bodyless binary-file preparation operation."""

    version: Version = 0
    checksum: Checksum
    content_type: MediaType
    content_encoding: str | None = None


class ParameterBlobStatus(StrEnum):
    """Availability states reported by the blob service."""

    PENDING = "Pending"
    DEFERRED = "Deferred"
    UNKNOWN = "Unknown"
    UPLOADED = "Uploaded"


class ParameterBlobAssociation(SDKModel):
    """Project/application association for one blob reference."""

    id: PositiveID = Field(alias="ID")
    created_at: datetime = Field(alias="CreatedAt")
    updated_at: datetime = Field(alias="UpdatedAt")
    deleted_at: datetime | None = Field(alias="DeletedAt")
    project: str
    blob_ref_id: PositiveID = Field(alias="blobRefId")
    application: str
    collection: str
    sub_ref: str = Field(alias="subRef")


class ParameterBlobRef(SDKModel):
    """A blob reference; only Uploaded establishes binary availability."""

    id: PositiveID = Field(alias="ID")
    created_at: datetime = Field(alias="CreatedAt")
    updated_at: datetime = Field(alias="UpdatedAt")
    deleted_at: datetime | None = Field(alias="DeletedAt")
    checksum: str
    owner_project: str = Field(alias="ownerProject")
    signed_url: str = Field(alias="signedUrl")
    status: ParameterBlobStatus
    association: list[ParameterBlobAssociation] = Field(default_factory=list)


class ParameterBlobListData(SDKModel):
    """Completion flag and references for the requested trees."""

    is_complete: bool = Field(alias="isComplete", strict=True)
    blob_refs: list[ParameterBlobRef] = Field(alias="blobRefs")


class ParameterTreeListResponse(SDKModel):
    """Tree listing; an empty array is a valid result."""

    data: list[str]


class ParameterTreeCreateResponse(SDKModel):
    """Name acknowledged by a bodyless root creation."""

    data: str


class ParameterNodeResponse(SDKModel):
    """Recursive tree read or one child-write result."""

    data: ParameterNode


class ParameterDeleteResponse(SDKModel):
    """Confirmed root or child deletion."""

    data: Literal["ok"]


class ParameterUploadResponse(SDKModel):
    """Prepared binary FileNode with a reference and optional authorization."""

    data: ParameterNode

    @model_validator(mode="after")
    def validate_authorization(self) -> Self:
        """Reject incomplete or non-file preparation acknowledgments."""
        if self.data.node_type != ParameterNodeType.FILE or not self.data.blob_ref_id:
            message = "Preparation requires a FileNode with a blob_ref_id"
            raise ValueError(message)
        return self


class ParameterCommitData(SDKModel):
    """Positive upload completion acknowledgment."""

    upload: Literal[True]

    @field_validator("upload", mode="before")
    @classmethod
    def require_true(cls, value: object) -> object:
        """Require JSON true rather than a truthy or coercible value."""
        if value is not True:
            message = "Completion acknowledgment must be true"
            raise ValueError(message)
        return value


class ParameterCommitResponse(SDKModel):
    """Result of a bodyless upload-completion operation."""

    data: ParameterCommitData


class ParameterBlobListResponse(SDKModel):
    """Blob listing with exact status and checksum metadata."""

    data: ParameterBlobListData


class ParameterErrorResponse(SDKModel):
    """The service's error envelope, never returned as a successful result."""

    error: str


class ParameterUploadOptions(SDKModel):
    """Exact local selection, explicit recreation and hierarchy mode."""

    tree_names: tuple[str, ...] = ()
    delete_existing_trees: bool = Field(default=False, strict=True)
    as_folder: bool = Field(default=True, strict=True)

    @field_validator("tree_names")
    @classmethod
    def unique_names(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Deduplicate exact names in caller order."""
        return tuple(dict.fromkeys(values))


class ParameterSkipReason(StrEnum):
    """Why an inspected local entry was not submitted."""

    UNMATCHED_TREE = "unmatched_tree"
    ROOT_FILE = "root_file"
    SYMBOLIC_LINK = "symbolic_link"
    SPECIAL_ENTRY = "special_entry"
    LEGACY_ATTRIBUTE_FILE = "legacy_attribute_file"


class ParameterUploadStage(StrEnum):
    """Attributable source, platform and storage stages."""

    VALIDATE_SOURCE = "validate_source"
    DELETE_TREE = "delete_tree"
    CREATE_TREE = "create_tree"
    CREATE_NODE = "create_node"
    READ_FILE = "read_file"
    PREPARE_UPLOAD = "prepare_upload"
    TRANSFER_BLOB = "transfer_blob"
    CONFIRM_UPLOAD = "confirm_upload"
    VERIFY_BLOB = "verify_blob"


class _ParameterSnapshot(SDKModel):
    """Immutable base for result items and snapshots."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class ParameterFileUploadResult(_ParameterSnapshot):
    """One acknowledged file with the checksum of its original bytes."""

    tree_path: str
    storage: Literal["inline", "blob"]
    checksum: Checksum
    blob_ref_id: BlobID | None = None


class ParameterSkippedEntry(_ParameterSnapshot):
    """Relative source path and reason for skipping it."""

    path: str
    reason: ParameterSkipReason


class ParameterUploadResult(_ParameterSnapshot):
    """Immutable snapshot of known completed operations and inspected skips."""

    selected_trees: tuple[str, ...] = ()
    completed_trees: tuple[str, ...] = ()
    completed_files: tuple[ParameterFileUploadResult, ...] = ()
    created_directories: tuple[str, ...] = ()
    deleted_trees: tuple[str, ...] = ()
    skipped_entries: tuple[ParameterSkippedEntry, ...] = ()


class ParameterUploadFailure(_ParameterSnapshot):
    """Last attributable path/stage with a redacted cause description."""

    path: str
    stage: ParameterUploadStage
    message: str
