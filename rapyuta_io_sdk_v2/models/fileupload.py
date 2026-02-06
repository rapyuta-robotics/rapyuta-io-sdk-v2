"""
Pydantic models for FileUpload and SharedURL resource validation.

This module contains Pydantic models that correspond to the FileUpload and SharedURL
JSON schemas, providing validation for device file upload resources.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject

DEFAULT_LOG_UPLOAD_BANDWIDTH = 1 * 1024 * 1024


class FileUploadRequest(BaseModel):
    """Request model for creating a file upload.

    This is the request schema used when creating a new file upload.
    Similar to LogsUploadRequest in the old SDK.

    :param device_path: Absolute path of file on device (required)
    :param file_name: Name of the file in cloud storage (optional, derived from device_path if not provided)
    :param max_upload_rate: Network bandwidth to be used for upload in bytes/sec (default: 1MB/s)
    :param override: If true, overrides the destination file (default: False)
    :param purge_after: If true, purges the log file after upload (default: False)
    :param metadata: Key/value pairs to be associated with log file (optional)
    """

    model_config = ConfigDict(populate_by_name=True)

    device_path: str = Field(
        description="Absolute path of file on device",
        alias="file_path",
    )
    file_name: str | None = Field(
        default=None,
        description="Name of the file in cloud storage",
        alias="file_name",
    )
    max_upload_rate: int = Field(
        default=DEFAULT_LOG_UPLOAD_BANDWIDTH,
        description="Network bandwidth for upload (bytes/sec)",
        alias="max_upload_rate",
    )
    override: bool = Field(
        default=False,
        description="Override destination file if exists",
    )
    purge_after: bool = Field(
        default=False,
        description="Purge file after upload",
        alias="purge_after",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Custom metadata key/value pairs",
    )

    @field_validator("device_path")
    @classmethod
    def validate_device_path(cls, v: str) -> str:
        """Validate that device_path is a non-empty string."""
        if not v or not isinstance(v, str) or v.strip() == "":
            raise ValueError("device_path must be a valid non-empty string")
        return v


class SharedURLRequest(BaseModel):
    """Request model for creating a shared URL.

    This is the request schema used when creating a new shared URL for a file upload.
    Similar to SharedURL constructor in the old SDK.

    :param expiry_time: Datetime when the shared URL expires (required)
    """

    model_config = ConfigDict(populate_by_name=True)

    expiry_time: datetime = Field(
        description="When the shared URL expires",
        alias="expiryTime",
    )

    @field_validator("expiry_time")
    @classmethod
    def validate_expiry_time(cls, v: datetime) -> datetime:
        """Validate that expiry_time is a valid datetime object."""
        if not isinstance(v, datetime) or v is None:
            raise ValueError("expiry_time must be a valid datetime object")
        return v


class FileUploadSpec(BaseModel):
    """Specification for FileUpload resource."""

    model_config = ConfigDict(populate_by_name=True)

    device_guid: str | None = Field(
        default=None,
        description="Device the file belongs to",
        alias="device_guid",
    )
    file_name: str | None = Field(
        default=None,
        description="Name of the file (extracted from file_path if not provided)",
        alias="file_name",
    )
    file_path: str = Field(
        description="Path on device where file is located",
        alias="file_path",
    )
    upload_url: str | None = Field(
        default=None,
        description="Pre-signed URL for upload (response only)",
        alias="upload_url",
    )
    blob_ref_id: int | None = Field(
        default=None,
        description="Cloud storage reference (response only)",
        alias="blob_ref_id",
    )
    max_upload_rate: int | None = Field(
        default=None,
        description="Maximum upload rate in bytes/sec",
        alias="max_upload_rate",
    )
    override: bool | None = Field(
        default=None,
        description="Whether to override existing file",
    )
    purge_after: bool | None = Field(
        default=None,
        description="Whether to purge file after download",
        alias="purge_after",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Custom metadata",
    )
    shared_urls: list["SharedURL"] | None = Field(
        default=None,
        description="List of shared URLs",
        alias="sharedURLs",
    )


class FileUploadStatus(BaseModel):
    """Status for FileUpload resource."""

    model_config = ConfigDict(populate_by_name=True)

    status: (
        Literal["PENDING", "IN PROGRESS", "FAILED", "COMPLETED", "CANCELLED"] | None
    ) = Field(
        default=None,
        description="Upload status",
    )
    total_size: int | None = Field(
        default=None,
        description="File size in bytes",
        alias="total_size",
    )
    uploaded_bytes: int | None = Field(
        default=None,
        description="Number of bytes uploaded",
        alias="uploaded_bytes",
    )
    error_message: str | None = Field(
        default=None,
        description="Error details if failed",
        alias="error_message",
    )
    error_code: str | None = Field(
        default=None,
        description="Error code for failures",
        alias="error_code",
    )


class SharedURLSpec(BaseModel):
    """Specification for SharedURL resource."""

    model_config = ConfigDict(populate_by_name=True)

    file_upload_guid: str | None = Field(
        default=None,
        description="File upload this URL belongs to",
        alias="fileUploadGUID",
    )
    expiry_time: datetime = Field(
        description="When the shared URL expires",
        alias="expiryTime",
    )
    signed_url: str | None = Field(
        default=None,
        description="The signed download URL (response only)",
        alias="signedURL",
    )


class SharedURL(BaseObject):
    """SharedURL model."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["DeviceSharedURL"] | None = "DeviceSharedURL"
    metadata: BaseMetadata | None = Field(
        default=None,
        description="Metadata for the SharedURL resource",
    )
    spec: SharedURLSpec = Field(description="Specification for the SharedURL resource")


class SharedURLList(BaseList[SharedURL]):
    """List of shared URLs using BaseList."""

    pass


class FileUpload(BaseObject):
    """FileUpload model."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["DeviceFileUpload"] | None = "DeviceFileUpload"
    metadata: BaseMetadata | None = Field(
        default=None,
        description="Metadata for the FileUpload resource",
    )
    spec: FileUploadSpec = Field(description="Specification for the FileUpload resource")
    status: FileUploadStatus | None = Field(default=None)


class FileUploadList(BaseList[FileUpload]):
    """List of file uploads using BaseList."""

    pass
