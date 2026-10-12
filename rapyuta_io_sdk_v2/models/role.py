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

"""Resource validation models for role."""
# Lifecycle helper imports remain local to keep model modules independent.

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from rapyuta_io_sdk_v2.models.applier import ResourceCapabilities, ResourceContext
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.resource import ResourceMethods
from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client


class Rule(SDKModel):
    """Resources and actions permitted by a role."""

    resource: str
    instances: list[str] | None = None
    actions: list[str] | None = None


class RoleSpec(SDKModel):
    """Role description and authorization rules."""

    description: str | None = None
    rules: list[Rule] | None = None


class Role(ResourceMethods, BaseObject):
    """Named collection of authorization rules."""

    KIND: ClassVar[str] = "Role"
    CAPABILITIES: ClassVar[ResourceCapabilities] = ResourceCapabilities(
        create=True, update=True, delete=True, apply_policy="create_or_update"
    )

    kind: Literal["Role"] | None = "Role"
    metadata: BaseMetadata
    spec: RoleSpec

    def create_object(self, client: Client, *, context: ResourceContext) -> Role:
        """Create a Role in the selected organization."""
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
            lambda: client.create_role(payload, **organization_options(context)),
        )

    async def create_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> Role:
        """Create a Role through the native asynchronous endpoint."""
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
            lambda: client.create_role(payload, **organization_options(context)),
        )

    def update_object(self, client: Client, *, context: ResourceContext) -> Role:
        """Update a Role in the selected organization."""
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
            lambda: client.update_role(payload, **organization_options(context)),
        )

    async def update_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> Role:
        """Update a Role through the native asynchronous endpoint."""
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
            lambda: client.update_role(payload, **organization_options(context)),
        )

    def _delete_object(self, client: Client, *, context: ResourceContext) -> None:
        """Delete this Role by its scoped name."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write,
        )

        metadata = self.metadata
        record_write(
            context,
            "deleted",
            lambda: client.delete_role(metadata.name, **organization_options(context)),
        )

    async def _delete_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> None:
        """Delete this Role through the native async client."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write_async,
        )

        metadata = self.metadata
        await record_write_async(
            context,
            "deleted",
            lambda: client.delete_role(metadata.name, **organization_options(context)),
        )


class RoleList(BaseList[Role]):
    """Paginated role resources."""
