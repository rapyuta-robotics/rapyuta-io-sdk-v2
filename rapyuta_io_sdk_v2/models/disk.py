"""
Pydantic models for Disk resource validation.

This module contains Pydantic models that correspond to the Disk JSON schema,
providing validation for Disk resources to help users identify missing or
incorrect fields.
"""

from typing import Literal
from pydantic import BaseModel, Field, field_validator

from rapyuta_io_sdk_v2.models.utils import BaseMetadata, BaseList, Runtime


class DiskBound(BaseModel):
    deployment_guid: str | None
    deployment_name: str | None


class DiskSpec(BaseModel):
    """Specification for Disk resource."""

    runtime: Runtime = Field(
        default="cloud", description="Runtime environment for the disk"
    )
    capacity: int | float | None = Field(default=None, description="Disk capacity in GB")

    @field_validator("capacity")
    @classmethod
    def validate_capacity(cls, v):
        """Validate disk capacity against allowed values."""
        if v is not None:
            allowed_capacities = [4, 8, 16, 32, 64, 128, 256, 512]
            if v not in allowed_capacities:
                raise ValueError(
                    f"Disk capacity must be one of: {allowed_capacities}. Got: {v}"
                )
        return v


class DiskStatus(BaseModel):
    status: Literal["Available", "Bound", "Released", "Failed", "Pending"]
    capacityUsed: float | None = Field(
        default=None, description="Used disk capacity in GB"
    )
    capacityAvailable: float | None = Field(
        default=None, description="Available disk capacity in GB"
    )
    errorCode: str | None = Field(default=None, description="Error code if any")
    diskBound: DiskBound | None = Field(
        default=None, description="Disk bound information"
    )

    @field_validator("diskBound", mode="before")
    @classmethod
    def normalize_disk_bound(cls, v):
        """Convert empty dict to None for diskBound field."""
        if isinstance(v, dict) and not v:
            return None
        return v


class Disk(BaseModel):
    """Disk model."""

    apiVersion: str | None = Field(default="apiextensions.rapyuta.io/v1")
    kind: str | None = Field(default="Disk")
    metadata: BaseMetadata = Field(description="Metadata for the Disk resource")
    spec: DiskSpec = Field(description="Specification for the Disk resource")
    status: DiskStatus | None = Field(default=None)


class DiskList(BaseList[Disk]):
    """List of disks using BaseList."""

    pass
