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

"""Pydantic models for StaticRoute resource validation.

This module contains Pydantic models that correspond to the StaticRoute JSON schema,
providing validation for StaticRoute resources to help users identify missing or
incorrect fields.
"""
# Lifecycle helper imports remain local to keep model modules independent.

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field, field_validator

from rapyuta_io_sdk_v2.models.applier import (
    ResourceCapabilities,
    ResourceContext,
    ResourceOutcome,
)
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.resource import ResourceMethods

from .utils import BaseList, BaseMetadata, BaseObject

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client


class StaticRouteSpec(SDKModel):
    """Specification for StaticRoute resource."""

    url: str | None = Field(default=None, description="URL for the static route")
    source_ip_range: list[str] | None = Field(
        default=None,
        description="List of source IP ranges in CIDR notation",
        alias="sourceIPRange",
    )

    @field_validator("source_ip_range")
    @staticmethod
    def validate_ip_ranges(v: list[str] | None) -> list[str] | None:
        """Validate IP range format (CIDR notation).

        Args:
            v: Field value supplied to the validator.
        """
        ip_pattern = (
            r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}(?:/([1-9]|1\d|2\d|3[0-2]))?$"
        )
        if v is not None:
            for ip_range in v:
                if not re.match(ip_pattern, ip_range):
                    message = (
                        f"Invalid IP range format: {ip_range}. "
                        "Must be a valid CIDR notation (e.g., 192.168.1.0/24)"
                    )
                    raise ValueError(message)
        return v


class StaticRouteStatus(SDKModel):
    """Status for StaticRoute resource."""

    status: Literal["Available", "Unavailable"] | None = Field(
        default=None, description="Status of the static route"
    )
    package_guid: str | None = Field(
        default=None,
        description="Package ID associated with the static route",
        alias="packageID",
    )
    deployment_guid: str | None = Field(
        default=None,
        description="Deployment ID associated with the static route",
        alias="deploymentID",
    )


class StaticRoute(ResourceMethods, BaseObject):
    """StaticRoute resource model for validation.

    This model validates StaticRoute resources according to the JSON schema,
    helping users identify missing or incorrect configuration.
    A named route for the Deployment endpoint.
    """

    KIND: ClassVar[str] = "StaticRoute"
    CAPABILITIES: ClassVar[ResourceCapabilities] = ResourceCapabilities(
        create=True,
        update=True,
        delete=True,
        apply_policy="create_or_update",
    )

    kind: Literal["StaticRoute"] = Field(
        default="StaticRoute", description="Resource kind, must be 'StaticRoute'"
    )
    metadata: BaseMetadata = Field(description="Metadata for the StaticRoute resource")
    spec: StaticRouteSpec | None = Field(
        default=None, description="Specification for the StaticRoute resource"
    )
    status: StaticRouteStatus | None = Field(
        default=None, description="Status of the StaticRoute resource"
    )

    def create_object(self, client: Client, *, context: ResourceContext) -> StaticRoute:
        """Create a route using its logical manifest name."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write,
            scoped_copy,
        )
        from rapyuta_io_sdk_v2.apply._resources.staticroute import (  # noqa: PLC0415
            _selected_context,
        )

        context = _selected_context(self, client, context)
        payload = scoped_copy(self, context)
        return record_write(
            context,
            "created",
            lambda: client.create_staticroute(payload, **project_options(context)),
        )

    async def create_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> StaticRoute:
        """Create a route with the native asynchronous endpoint."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write_async,
            scoped_copy,
        )
        from rapyuta_io_sdk_v2.apply._resources.staticroute import (  # noqa: PLC0415
            _selected_context,
        )

        context = _selected_context(self, client, context)
        payload = scoped_copy(self, context)
        return await record_write_async(
            context,
            "created",
            lambda: client.create_staticroute(payload, **project_options(context)),
        )

    def update_object(self, client: Client, *, context: ResourceContext) -> StaticRoute:
        """Update using the canonical server-side routing name."""
        from rapyuta_io_sdk_v2.apply._resources.staticroute import update_staticroute  # noqa: PLC0415

        return update_staticroute(client, self, context=context)

    async def update_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> StaticRoute:
        """Update a route with native async resolution and write calls."""
        from rapyuta_io_sdk_v2.apply._resources.staticroute import (  # noqa: PLC0415
            update_staticroute_async,
        )

        return await update_staticroute_async(client, self, context=context)

    def apply(self, client: Client, *, context: ResourceContext) -> ResourceOutcome:
        """Apply a route with common create/update conflict policy."""
        from rapyuta_io_sdk_v2.apply._lifecycle import apply_resource  # noqa: PLC0415

        return apply_resource(self, client, context=context)

    async def apply_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> ResourceOutcome:
        """Apply a route with common native async create/update policy."""
        from rapyuta_io_sdk_v2.apply._lifecycle import apply_resource_async  # noqa: PLC0415

        return await apply_resource_async(self, client, context=context)

    def _delete_object(self, client: Client, *, context: ResourceContext) -> None:
        """Resolve and delete this route's canonical platform name."""
        from rapyuta_io_sdk_v2.apply._resources.staticroute import delete_staticroute  # noqa: PLC0415

        delete_staticroute(client, self, context=context)

    async def _delete_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> None:
        """Resolve and delete the route through native async calls."""
        from rapyuta_io_sdk_v2.apply._resources.staticroute import (  # noqa: PLC0415
            delete_staticroute_async,
        )

        await delete_staticroute_async(client, self, context=context)


class StaticRouteList(BaseList[StaticRoute]):
    """Paginated static route resources."""
