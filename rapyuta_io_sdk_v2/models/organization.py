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

"""Resource validation models for organization."""
# Lifecycle helper imports remain local to keep model modules independent.

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field

from rapyuta_io_sdk_v2.models.applier import (
    DependencyReference,
    ResourceCapabilities,
    ResourceContext,
    ResourceReference,
    ResourceScope,
)
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.resource import ResourceMethods

from .utils import BaseMetadata, BaseObject, Subject

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client


class OrganizationMember(SDKModel):
    """Organization subject and its assigned roles."""

    subject: Subject
    role_names: list[str] = Field(alias="roleNames")


class OrganizationSpec(SDKModel):
    """Members authorized within an organization."""

    members: list[OrganizationMember]


class Organization(ResourceMethods, BaseObject):
    """Organization identity and membership manifest."""

    KIND: ClassVar[str] = "Organization"
    CAPABILITIES: ClassVar[ResourceCapabilities] = ResourceCapabilities(
        create=False,
        update=True,
        delete=False,
        apply_policy="update_only",
    )

    kind: Literal["Organization"] | None = "Organization"
    metadata: BaseMetadata
    spec: OrganizationSpec

    def resource_dependencies(
        self, *, scope: ResourceScope | None = None
    ) -> tuple[DependencyReference, ...]:
        """Declare explicit organization members and their assigned roles."""
        del scope
        dependencies: list[DependencyReference] = []
        for member in self.spec.members:
            subject = member.subject
            if subject.kind is not None and (
                subject.name is not None or subject.guid is not None
            ):
                dependencies.append(
                    DependencyReference(
                        reference=ResourceReference(
                            kind=subject.kind.lower(),
                            name=subject.name,
                            guid=subject.guid,
                        )
                    )
                )
            dependencies.extend(
                DependencyReference(
                    reference=ResourceReference(kind="role", name=role_name)
                )
                for role_name in member.role_names
            )
        return tuple(dependencies)

    def update_object(
        self, client: Client, *, context: ResourceContext
    ) -> Organization:
        """Update this identified Organization; creation is unsupported."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            record_write,
            scoped_copy,
        )

        payload = scoped_copy(
            self,
            context,
            include_organization=False,
            include_project=False,
        )
        organization_guid = payload.metadata.guid
        if organization_guid is None:
            msg = "Organization update requires metadata.guid"
            raise ValueError(msg)
        return record_write(
            context,
            "updated",
            lambda: client.update_organization(payload, organization_guid),
        )

    async def update_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> Organization:
        """Update this Organization through the native asynchronous operation."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            record_write_async,
            scoped_copy,
        )

        payload = scoped_copy(
            self,
            context,
            include_organization=False,
            include_project=False,
        )
        organization_guid = payload.metadata.guid
        if organization_guid is None:
            msg = "Organization update requires metadata.guid"
            raise ValueError(msg)
        return await record_write_async(
            context,
            "updated",
            lambda: client.update_organization(payload, organization_guid),
        )
