# Copyright 2026 Rapyuta Robotics
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Pydantic models for Disk resource validation.

This module contains Pydantic models that correspond to the Disk JSON schema,
providing validation for Disk resources to help users identify missing or
incorrect fields.
"""
# Lifecycle helper imports remain local to keep model modules independent.

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import ConfigDict, Field, field_validator

from rapyuta_io_sdk_v2.models.applier import ResourceCapabilities, ResourceContext
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.resource import ResourceMethods
from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject, Runtime

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client


class DiskSpec(SDKModel):
    """Specification for Disk resource."""

    runtime: Runtime = Field(
        default="cloud", description="Runtime environment for the disk"
    )
    capacity: int = Field(multiple_of=2, ge=4, le=512)


class DiskBound(SDKModel):
    """Deployment currently bound to a disk."""

    deployment_guid: str | None
    deployment_name: str | None


class DiskStatus(SDKModel):
    """Disk lifecycle, capacity usage, and deployment binding."""

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
    def normalize_disk_bound(value: object) -> object:
        """Convert empty dict to None for diskBound field.

        Args:
            value: Field value supplied to the validator.
        """
        if isinstance(value, dict) and not value:
            return None
        return value


class Disk(ResourceMethods, BaseObject):
    """Disk model."""

    KIND: ClassVar[str] = "Disk"
    CAPABILITIES: ClassVar[ResourceCapabilities] = ResourceCapabilities(
        create=True,
        update=False,
        delete=True,
        apply_policy="create_or_exists",
        readiness_kind="disk",
    )

    model_config = ConfigDict(extra="forbid")

    kind: Literal["Disk"] | None = "Disk"
    metadata: BaseMetadata = Field(description="Metadata for the Disk resource")
    spec: DiskSpec = Field(description="Specification for the Disk resource")
    status: DiskStatus | None = Field(default=None)

    def readiness_state(self) -> tuple[str | None, bool, bool]:
        """Return the observed state, readiness, and terminal failure flags."""
        status = self.status.status if self.status is not None else None
        return status, status in {"Available", "Released"}, status == "Failed"

    def create_object(self, client: Client, *, context: ResourceContext) -> Disk:
        """Create a Disk through the typed SDK operation."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write,
            scoped_context,
            scoped_copy,
        )

        context = scoped_context(self, context)
        payload = scoped_copy(self, context)
        return record_write(
            context,
            "created",
            lambda: client.create_disk(payload, **project_options(context)),
        )

    async def create_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> Disk:
        """Create a Disk through the native asynchronous SDK operation."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write_async,
            scoped_context,
            scoped_copy,
        )

        context = scoped_context(self, context)
        payload = scoped_copy(self, context)
        return await record_write_async(
            context,
            "created",
            lambda: client.create_disk(payload, **project_options(context)),
        )

    def _delete_object(self, client: Client, *, context: ResourceContext) -> None:
        """Delete this Disk by its scoped name."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write,
        )

        metadata = self.metadata
        record_write(
            context,
            "deleted",
            lambda: client.delete_disk(metadata.name, **project_options(context)),
        )

    async def _delete_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> None:
        """Delete this Disk through the native async client."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write_async,
        )

        metadata = self.metadata
        await record_write_async(
            context,
            "deleted",
            lambda: client.delete_disk(metadata.name, **project_options(context)),
        )


class DiskList(BaseList[Disk]):
    """List of disks using BaseList."""
