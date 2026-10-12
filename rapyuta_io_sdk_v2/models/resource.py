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

"""Field-free paired lifecycle methods for managed SDK resources."""
# Lifecycle helper imports remain local to keep model modules independent.

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol, cast

from rapyuta_io_sdk_v2.apply.errors import UnsupportedResourceOperationError
from rapyuta_io_sdk_v2.models.applier import (
    DependencyReference,
    ResourceCapabilities,
    ResourceContext,
    ResourceIdentity,
    ResourceOutcome,
    ResourceScope,
)

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.models.base import SDKModel
    from rapyuta_io_sdk_v2.models.utils import BaseMetadata


class _ResourceData(Protocol):
    metadata: BaseMetadata | None


class Resource(Protocol):
    """Typing-only common contract for resources with lifecycle operations."""

    def resource_identity(
        self, *, scope: ResourceScope | None = None
    ) -> ResourceIdentity:
        """Return the scoped structured identity of this resource."""
        ...

    def resource_dependencies(
        self, *, scope: ResourceScope | None = None
    ) -> tuple[DependencyReference, ...]:
        """Return explicitly modeled resource prerequisites."""
        ...

    def resource_capabilities(self) -> ResourceCapabilities:
        """Return immutable operation capabilities declared by the model."""
        ...

    def retention_policy(self) -> str:
        """Return the resource's explicit deletion policy."""
        ...

    def create_object(self, client: Client, *, context: ResourceContext) -> SDKModel:
        """Create this resource with the supplied synchronous client."""
        ...

    def update_object(self, client: Client, *, context: ResourceContext) -> SDKModel:
        """Update this resource with the supplied synchronous client."""
        ...

    def delete_object(
        self, client: Client, *, context: ResourceContext
    ) -> ResourceOutcome:
        """Delete this resource with the supplied synchronous client."""
        ...

    def apply(self, client: Client, *, context: ResourceContext) -> ResourceOutcome:
        """Apply this resource's declared synchronous policy."""
        ...

    async def create_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> SDKModel:
        """Create this resource with the supplied asynchronous client."""
        ...

    async def update_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> SDKModel:
        """Update this resource with the supplied asynchronous client."""
        ...

    async def delete_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> ResourceOutcome:
        """Delete this resource with the supplied asynchronous client."""
        ...

    async def apply_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> ResourceOutcome:
        """Apply this resource's declared asynchronous policy."""
        ...


class ResourceMethods:
    """Common lifecycle policy with explicit resource override hooks.

    Subclasses declare ``KIND`` and ``CAPABILITIES`` as ClassVars. This mixin
    defines methods only, so adding it does not alter Pydantic schemas or dumps.
    """

    KIND: ClassVar[str] = ""
    CAPABILITIES: ClassVar[ResourceCapabilities]

    def resource_identity(
        self, *, scope: ResourceScope | None = None
    ) -> ResourceIdentity:
        """Build the default named identity using the documented scope matrix."""
        data = cast("_ResourceData", self)
        metadata = data.metadata
        if metadata is None:
            msg = f"{self.KIND} metadata is required for identity"
            raise ValueError(msg)
        kind = self.KIND.lower()
        org_scope = kind in {
            "project",
            "usergroup",
            "role",
            "rolebinding",
            "serviceaccount",
            "package",
            "deployment",
            "disk",
            "network",
            "staticroute",
            "secret",
        }
        project_scope = kind in {
            "package",
            "deployment",
            "disk",
            "network",
            "staticroute",
            "secret",
        }
        selected = scope or ResourceScope()
        organization_guid = metadata.organization_guid or selected.organization_guid
        project_guid = metadata.project_guid or selected.project_guid
        effective_scope = ResourceScope(
            organization_guid=organization_guid if org_scope else None,
            project_guid=project_guid if project_scope else None,
        )
        return ResourceIdentity(
            kind=kind,
            scope=effective_scope,
            name=metadata.name,
            guid=metadata.guid,
            version=None,
        )

    def resource_dependencies(
        self, *, scope: ResourceScope | None = None
    ) -> tuple[DependencyReference, ...]:
        """Return no prerequisites unless a concrete resource declares them."""
        del scope
        return ()

    def resource_capabilities(self) -> ResourceCapabilities:
        """Return this model's immutable, non-serialized capability declaration."""
        return self.CAPABILITIES

    def retention_policy(self) -> str:
        """Return the explicit deletion label policy, defaulting to delete."""
        metadata = cast("_ResourceData", self).metadata
        if metadata is None or metadata.labels is None:
            return "delete"
        return (
            "retain"
            if metadata.labels.get("rapyuta.io/deletionPolicy") == "retain"
            else "delete"
        )

    def create_object(self, client: Client, *, context: ResourceContext) -> SDKModel:
        """Raise a typed unsupported-operation error before any transport call."""
        del client, context
        msg = "create"
        raise self._unsupported(msg)

    def update_object(self, client: Client, *, context: ResourceContext) -> SDKModel:
        """Raise a typed unsupported-operation error before any transport call."""
        del client, context
        msg = "update"
        raise self._unsupported(msg)

    async def create_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> SDKModel:
        """Raise a typed unsupported-operation error before any transport call."""
        del client, context
        msg = "create"
        raise self._unsupported(msg)

    async def update_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> SDKModel:
        """Raise a typed unsupported-operation error before any transport call."""
        del client, context
        msg = "update"
        raise self._unsupported(msg)

    def _delete_object(self, client: Client, *, context: ResourceContext) -> None:
        """Declare the unsupported deletion hook for a resource model."""
        del client, context
        msg = "delete"
        raise self._unsupported(msg)

    async def _delete_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> None:
        """Declare the unsupported asynchronous deletion hook."""
        del client, context
        msg = "delete"
        raise self._unsupported(msg)

    def delete_object(
        self, client: Client, *, context: ResourceContext
    ) -> ResourceOutcome:
        """Apply retention, absence, and typed delete-hook policy."""
        from rapyuta_io_sdk_v2.apply._lifecycle import delete_resource  # noqa: PLC0415

        return delete_resource(self, client, context=context)

    async def delete_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> ResourceOutcome:
        """Apply asynchronous retention and delete-hook policy."""
        from rapyuta_io_sdk_v2.apply._lifecycle import delete_resource_async  # noqa: PLC0415

        return await delete_resource_async(self, client, context=context)

    def apply(self, client: Client, *, context: ResourceContext) -> ResourceOutcome:
        """Execute the model's declared synchronous create/update policy."""
        from rapyuta_io_sdk_v2.apply._lifecycle import apply_resource  # noqa: PLC0415

        return apply_resource(self, client, context=context)

    async def apply_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> ResourceOutcome:
        """Execute the model's declared asynchronous create/update policy."""
        from rapyuta_io_sdk_v2.apply._lifecycle import apply_resource_async  # noqa: PLC0415

        return await apply_resource_async(self, client, context=context)

    def _unsupported(self, operation: str) -> UnsupportedResourceOperationError:
        return UnsupportedResourceOperationError(
            f"{self.KIND} does not support {operation}",
            identity=self.resource_identity(),
            operation=operation,
        )


__all__ = ["Resource", "ResourceMethods"]
