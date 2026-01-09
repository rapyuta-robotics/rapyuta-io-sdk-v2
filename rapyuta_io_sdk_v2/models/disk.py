"""
Pydantic models for Disk resource validation.

This module contains Pydantic models that correspond to the Disk JSON schema,
providing validation for Disk resources to help users identify missing or
incorrect fields.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject, Runtime


class DiskSpec(BaseModel):
    """Specification for Disk resource."""

    runtime: Runtime = Field(
        default="cloud", description="Runtime environment for the disk"
    )
    capacity: int = Field(multiple_of=2, ge=4, le=512)


class DiskBound(BaseModel):
    deployment_guid: str | None
    deployment_name: str | None


class DiskStatus(BaseModel):
    status: Literal["Available", "Bound", "Released", "Failed", "Pending"]
    capacity_used: float | None = Field(
        default=None,
        description="Used disk capacity in GB",
        alias="capacityUsed",
    )
    capacity_available: float | None = Field(
        default=None,
        description="Available disk capacity in GB",
        alias="capacityAvailable",
    )
    error_code: str | None = Field(
        default=None, description="Error code if any", alias="errorCode"
    )
    disk_bound: DiskBound | None = Field(
        default=None,
        description="Disk bound information",
        alias="diskBound",
    )

    @field_validator("disk_bound", mode="before")
    @staticmethod
    def normalize_disk_bound(value: Any) -> dict[str, Any] | None:
        """Convert empty dict to None for diskBound field."""
        if isinstance(value, dict) and not value:
            return None
        return value


class Disk(BaseObject):
    """Disk model."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["Disk"] | None = "Disk"
    metadata: BaseMetadata = Field(description="Metadata for the Disk resource")
    spec: DiskSpec = Field(description="Specification for the Disk resource")
    status: DiskStatus | None = Field(default=None)


class DiskList(BaseList[Disk]):
    """List of disks using BaseList."""

    pass
