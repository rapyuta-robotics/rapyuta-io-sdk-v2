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

"""Pydantic models for ServiceAccount resource validation.

This module mirrors the Go `ServiceAccount` and related types from the
`package extensions` snippet provided by the user.
"""
# Lifecycle helper imports remain local to keep model modules independent.

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field, field_validator

from rapyuta_io_sdk_v2.models.applier import (
    DependencyReference,
    ResourceCapabilities,
    ResourceContext,
    ResourceReference,
    ResourceScope,
)
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.resource import ResourceMethods
from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    Domain,
    named_resource_dependency,
)

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client


class ServiceAccountBinding(SDKModel):
    """Roles granted to a service account within a domain."""

    domain: Domain
    role_names: list[str] = Field(default_factory=list, alias="roleNames")


class ServiceAccountSpec(SDKModel):
    """Service account description and authorization bindings."""

    description: str | None = None
    roles: list[ServiceAccountBinding] | None = None


class ServiceAccount(ResourceMethods, BaseObject):
    """ServiceAccount model."""

    KIND: ClassVar[str] = "ServiceAccount"
    CAPABILITIES: ClassVar[ResourceCapabilities] = ResourceCapabilities(
        create=True, update=True, delete=True, apply_policy="create_or_update"
    )

    kind: Literal["ServiceAccount", "serviceaccount"] | None = "ServiceAccount"
    metadata: BaseMetadata
    spec: ServiceAccountSpec | None = None

    def resource_dependencies(
        self, *, scope: ResourceScope | None = None
    ) -> tuple[DependencyReference, ...]:
        """Declare each bound role and authorization domain prerequisite."""
        del scope
        dependencies: list[DependencyReference] = []
        for binding in (self.spec.roles or []) if self.spec is not None else []:
            domain = binding.domain
            if domain.kind is not None and (
                domain.name is not None or domain.guid is not None
            ):
                dependencies.append(
                    DependencyReference(
                        reference=ResourceReference(
                            kind=domain.kind.lower(), name=domain.name, guid=domain.guid
                        )
                    )
                )
            dependencies.extend(
                DependencyReference(
                    reference=ResourceReference(kind="role", name=role_name)
                )
                for role_name in binding.role_names
            )
        return tuple(dependencies)

    def create_object(
        self, client: Client, *, context: ResourceContext
    ) -> ServiceAccount:
        """Create a ServiceAccount in the selected organization."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write,
            scoped_context,
            scoped_copy,
        )

        context = scoped_context(self, context, include_project=False)
        payload = scoped_copy(self, context, include_project=False)
        return record_write(
            context,
            "created",
            lambda: client.create_service_account(
                payload, **organization_options(context)
            ),
        )

    async def create_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> ServiceAccount:
        """Create a ServiceAccount through the async SDK operation."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write_async,
            scoped_context,
            scoped_copy,
        )

        context = scoped_context(self, context, include_project=False)
        payload = scoped_copy(self, context, include_project=False)
        return await record_write_async(
            context,
            "created",
            lambda: client.create_service_account(
                payload, **organization_options(context)
            ),
        )

    def update_object(
        self, client: Client, *, context: ResourceContext
    ) -> ServiceAccount:
        """Update a ServiceAccount in the selected organization."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write,
            scoped_context,
            scoped_copy,
        )

        context = scoped_context(self, context, include_project=False)
        payload = scoped_copy(self, context, include_project=False)
        return record_write(
            context,
            "updated",
            lambda: client.update_service_account(
                payload, payload.metadata.name, **organization_options(context)
            ),
        )

    async def update_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> ServiceAccount:
        """Update a ServiceAccount through the native async SDK operation."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write_async,
            scoped_context,
            scoped_copy,
        )

        context = scoped_context(self, context, include_project=False)
        payload = scoped_copy(self, context, include_project=False)
        return await record_write_async(
            context,
            "updated",
            lambda: client.update_service_account(
                payload, payload.metadata.name, **organization_options(context)
            ),
        )

    def _delete_object(self, client: Client, *, context: ResourceContext) -> None:
        """Delete this ServiceAccount by its scoped name."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write,
        )

        metadata = self.metadata
        record_write(
            context,
            "deleted",
            lambda: client.delete_service_account(
                metadata.name, **organization_options(context)
            ),
        )

    async def _delete_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> None:
        """Delete this ServiceAccount through the native async client."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write_async,
        )

        metadata = self.metadata
        await record_write_async(
            context,
            "deleted",
            lambda: client.delete_service_account(
                metadata.name, **organization_options(context)
            ),
        )

    def list_dependencies(self) -> list[str] | None:
        """Return bound domains and roles in manifest order."""
        dependencies: list[str] = []
        if self.spec is None:
            return dependencies
        for binding in self.spec.roles or []:
            dependencies.extend(named_resource_dependency(binding.domain))
            dependencies.extend(f"role:{role}" for role in binding.role_names or [])
        return dependencies


class ServiceAccountList(BaseList[ServiceAccount]):
    """List of service accounts using BaseList."""


class ServiceAccountToken(SDKModel):
    """Token ownership and timezone-aware expiration settings."""

    owner: str | None = None
    expiry_at: datetime | None = Field(default=None, alias="expiry_at")

    @field_validator("expiry_at")
    @classmethod
    def check_expiry_at_iso8601(cls, v: datetime | None) -> datetime | None:
        """Require timezone information in token expiration timestamps.

        Args:
            v: Field value supplied to the validator.
        """
        if v is not None and v.tzinfo is None:
            message = "expiry_at must be an ISO8601 datetime with timezone info"
            raise ValueError(message)
        return v


class ServiceAccountTokenInfo(SDKModel):
    """Issued token identifier, credential, and expiration time."""

    id: int | None = None
    token: str | None = None
    expiry_at: datetime | None = Field(default=None, alias="expiry_at")

    @field_validator("expiry_at")
    @classmethod
    def check_expiry_at_iso8601(cls, v: datetime | None) -> datetime | None:
        """Require timezone information in token expiration timestamps.

        Args:
            v: Field value supplied to the validator.
        """
        if v is not None and v.tzinfo is None:
            message = "expiry_at must be an ISO8601 datetime with timezone info"
            raise ValueError(message)
        return v


class ServiceAccountTokenList(BaseList[ServiceAccountTokenInfo]):
    """List of service account tokens."""
