"""
Pydantic models for StaticRoute resource validation.

This module contains Pydantic models that correspond to the StaticRoute JSON schema,
providing validation for StaticRoute resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field, field_validator

from rapyuta_io_sdk_v2.models.utils import SDKModel

from .utils import BaseList, BaseMetadata, BaseObject


if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.context import RequestContext


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
        """Validate IP range format (CIDR notation)."""
        ip_pattern = (
            r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}(?:/([1-9]|1\d|2\d|3[0-2]))?$"
        )
        if v is not None:
            for ip_range in v:
                if not re.match(ip_pattern, ip_range):
                    raise ValueError(
                        f"Invalid IP range format: {ip_range}. Must be a valid CIDR notation (e.g., 192.168.1.0/24)"
                    )
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


class StaticRoute(BaseObject):
    """
    StaticRoute resource model for validation.

    This model validates StaticRoute resources according to the JSON schema,
    helping users identify missing or incorrect configuration.
    A named route for the Deployment endpoint.
    """

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

    resource_kind: ClassVar[str] = "StaticRoute"

    mutable: ClassVar[bool] = True

    def create(self, client: Client, *, context: RequestContext | None = None):
        return client.create_staticroute(self, context=context)

    def update(self, client: Client, *, context: RequestContext | None = None):
        return client.update_staticroute(self.metadata.name, self, context=context)

    async def create_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.create_staticroute(self, context=context)

    async def update_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.update_staticroute(self.metadata.name, self, context=context)

    def _delete(self, client: Client, *, context: RequestContext | None = None) -> None:
        client.delete_staticroute(self.metadata.name, context=context)

    async def _delete_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> None:
        await client.delete_staticroute(self.metadata.name, context=context)


class StaticRouteList(BaseList[StaticRoute]):
    pass
