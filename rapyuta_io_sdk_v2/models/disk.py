"""
Pydantic models for Disk resource validation.

This module contains Pydantic models that correspond to the Disk JSON schema,
providing validation for Disk resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import ConfigDict, Field, field_validator

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    Runtime,
    SDKModel,
)
from rapyuta_io_sdk_v2.resource_operations import Pause, ReadinessError, Request


class DiskSpec(SDKModel):
    """Specification for Disk resource."""

    runtime: Runtime = Field(
        default="cloud", description="Runtime environment for the disk"
    )
    capacity: int = Field(multiple_of=2, ge=4, le=512)


class DiskBound(SDKModel):
    deployment_guid: str | None
    deployment_name: str | None


class DiskStatus(SDKModel):
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

    resource_kind: ClassVar[str] = "Disk"

    endpoint: ClassVar[str] = "disk"

    def _wait(self, attempts: int, interval: float):
        for attempt in range(attempts):
            resource = yield Request(f"get_{self.endpoint}", (self.metadata.name,))
            status = getattr(resource.status, "status", None)
            if status in ("Available", "Released", "Bound"):
                return
            if status == "Failed":
                raise ReadinessError(f"{self.identity} failed")
            if attempt + 1 < attempts:
                yield Pause(interval)
        raise ReadinessError(f"{self.identity} readiness timed out")


class DiskList(BaseList[Disk]):
    """List of disks using BaseList."""

    pass
