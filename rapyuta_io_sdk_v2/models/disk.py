"""
Pydantic models for Disk resource validation.

This module contains Pydantic models that correspond to the Disk JSON schema,
providing validation for Disk resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

import asyncio
import time

from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import ConfigDict, Field, field_validator

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    Runtime,
    SDKModel,
)
from rapyuta_io_sdk_v2.resource_operations import ReadinessError


if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.context import RequestContext


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

    def create(self, client: Client, *, context: RequestContext | None = None):
        return client.create_disk(self, context=context)

    async def create_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.create_disk(self, context=context)

    def _delete(self, client: Client, *, context: RequestContext | None = None) -> None:
        client.delete_disk(self.metadata.name, context=context)

    async def _delete_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> None:
        await client.delete_disk(self.metadata.name, context=context)

    def wait(
        self,
        client: Client,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None = None,
    ) -> None:
        for attempt in range(attempts):
            resource = client.get_disk(self.metadata.name, context=context)
            status = resource.status.status if resource.status is not None else None
            if status in ("Available", "Released", "Bound"):
                return
            if status == "Failed":
                raise ReadinessError(f"{self.identity} failed")
            if attempt + 1 < attempts:
                time.sleep(interval)
        raise ReadinessError(f"{self.identity} readiness timed out")

    async def wait_async(
        self,
        client: AsyncClient,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None = None,
    ) -> None:
        for attempt in range(attempts):
            resource = await client.get_disk(self.metadata.name, context=context)
            status = resource.status.status if resource.status is not None else None
            if status in ("Available", "Released", "Bound"):
                return
            if status == "Failed":
                raise ReadinessError(f"{self.identity} failed")
            if attempt + 1 < attempts:
                await asyncio.sleep(interval)
        raise ReadinessError(f"{self.identity} readiness timed out")


class DiskList(BaseList[Disk]):
    """List of disks using BaseList."""

    pass
