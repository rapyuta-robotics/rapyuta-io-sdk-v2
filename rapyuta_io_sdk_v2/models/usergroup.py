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

"""Resource validation models for usergroup."""
# Lifecycle helper imports remain local to keep model modules independent.

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field

from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError
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
    Subject,
    named_resource_dependency,
)

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client


class UserGroupMemberCreate(SDKModel):
    """Subject and explicit roles added to a user group."""

    subject: Subject
    role_names: list[str] | None = Field(default=None, alias="roleNames")


class UserGroupMember(UserGroupMemberCreate):
    """User group member with explicit and inherited roles."""

    implicit_role_names: list[str] | None = Field(
        default=None, alias="implicitRoleNames"
    )


class UserGroupBinding(SDKModel):
    """Role assigned to a user group within a domain."""

    domain: Domain
    role_name: str = Field(alias="roleName")


class UserGroupSpec(SDKModel):
    """Group description, memberships, and authorization bindings."""

    description: str | None = None
    members_count: int | None = Field(default=None, alias="membersCount")
    members: list[UserGroupMember] | None = None
    roles: list[UserGroupBinding] | None = None


class UserGroupSpecCreate(UserGroupSpec):
    """Group creation fields with explicit membership assignments."""

    members: list[UserGroupMemberCreate] | None = None


class UserGroup(ResourceMethods, BaseObject):
    """Named user group and its membership and authorization settings."""

    KIND: ClassVar[str] = "UserGroup"
    CAPABILITIES: ClassVar[ResourceCapabilities] = ResourceCapabilities(
        create=True, update=True, delete=True, apply_policy="create_or_update"
    )

    kind: Literal["UserGroup"] | None = "UserGroup"
    metadata: BaseMetadata
    spec: UserGroupSpec

    def resource_dependencies(
        self, *, scope: ResourceScope | None = None
    ) -> tuple[DependencyReference, ...]:
        """Declare explicit member, role, and domain prerequisites."""
        del scope
        dependencies: list[DependencyReference] = []
        for member in self.spec.members or []:
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
                for role_name in member.role_names or []
            )
        for binding in self.spec.roles or []:
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
            dependencies.append(
                DependencyReference(
                    reference=ResourceReference(kind="role", name=binding.role_name)
                )
            )
        return tuple(dependencies)

    def create_object(self, client: Client, *, context: ResourceContext) -> UserGroup:
        """Create a UserGroup with its explicit membership request data."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write,
            scoped_context,
        )

        context = scoped_context(self, context, include_project=False)
        payload = self._create_payload(context)
        return record_write(
            context,
            "created",
            lambda: client.create_user_group(payload, **organization_options(context)),
        )

    async def create_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> UserGroup:
        """Create a UserGroup through the native asynchronous endpoint."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write_async,
            scoped_context,
        )

        context = scoped_context(self, context, include_project=False)
        payload = self._create_payload(context)
        return await record_write_async(
            context,
            "created",
            lambda: client.create_user_group(payload, **organization_options(context)),
        )

    def update_object(self, client: Client, *, context: ResourceContext) -> UserGroup:
        """Update a resolved UserGroup while preserving explicit memberships."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write,
            scoped_context,
            scoped_copy,
        )
        from rapyuta_io_sdk_v2.apply._resources.usergroup import (  # noqa: PLC0415
            resolve_usergroup_guid,
        )

        context = scoped_context(self, context, include_project=False)
        payload = scoped_copy(self, context, include_project=False)
        if payload.metadata.guid is None:
            group_guid = resolve_usergroup_guid(client, payload, context)
            if group_guid is None:
                msg = "UserGroup was not found for update"
                raise HttpNotFoundError(msg)
            payload = payload.model_copy(
                update={
                    "metadata": payload.metadata.model_copy(update={"guid": group_guid})
                }
            )
        return record_write(
            context,
            "updated",
            lambda: client.update_user_group(payload, **organization_options(context)),
        )

    async def update_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> UserGroup:
        """Update a UserGroup through the native asynchronous endpoint."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write_async,
            scoped_context,
            scoped_copy,
        )
        from rapyuta_io_sdk_v2.apply._resources.usergroup import (  # noqa: PLC0415
            resolve_usergroup_guid_async,
        )

        context = scoped_context(self, context, include_project=False)
        payload = scoped_copy(self, context, include_project=False)
        if payload.metadata.guid is None:
            group_guid = await resolve_usergroup_guid_async(client, payload, context)
            if group_guid is None:
                msg = "UserGroup was not found for update"
                raise HttpNotFoundError(msg)
            payload = payload.model_copy(
                update={
                    "metadata": payload.metadata.model_copy(update={"guid": group_guid})
                }
            )
        return await record_write_async(
            context,
            "updated",
            lambda: client.update_user_group(payload, **organization_options(context)),
        )

    def _delete_object(self, client: Client, *, context: ResourceContext) -> None:
        """Resolve this UserGroup's GUID and delete it."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write,
        )
        from rapyuta_io_sdk_v2.apply._resources.usergroup import (  # noqa: PLC0415
            resolve_usergroup_guid,
        )

        group_guid = resolve_usergroup_guid(client, self, context)
        if group_guid is None:
            msg = "UserGroup was not found"
            raise HttpNotFoundError(msg)
        record_write(
            context,
            "deleted",
            lambda: client.delete_user_group(
                self.metadata.name,
                group_guid,
                **organization_options(context),
            ),
        )

    async def _delete_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> None:
        """Delete this UserGroup through the native async client."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write_async,
        )
        from rapyuta_io_sdk_v2.apply._resources.usergroup import (  # noqa: PLC0415
            resolve_usergroup_guid_async,
        )

        group_guid = await resolve_usergroup_guid_async(client, self, context)
        if group_guid is None:
            msg = "UserGroup was not found"
            raise HttpNotFoundError(msg)
        await record_write_async(
            context,
            "deleted",
            lambda: client.delete_user_group(
                self.metadata.name,
                group_guid,
                **organization_options(context),
            ),
        )

    def _create_payload(self, context: ResourceContext) -> UserGroupCreate:
        """Build a private creation request preserving caller-supplied fields."""
        from rapyuta_io_sdk_v2.apply._resources.standard import scoped_copy  # noqa: PLC0415

        payload = scoped_copy(self, context, include_project=False)
        return UserGroupCreate.model_validate(payload.model_dump(mode="python"))


class UserGroupCreate(UserGroup):
    """User group creation manifest and resource prerequisites."""

    spec: UserGroupSpecCreate

    def list_dependencies(self) -> list[str] | None:
        """Return member, role, and domain dependencies in manifest order."""
        dependencies: list[str] = []
        for member in self.spec.members or []:
            dependencies.extend(named_resource_dependency(member.subject))
            dependencies.extend(f"role:{role}" for role in member.role_names or [])
        for binding in self.spec.roles or []:
            dependencies.extend(named_resource_dependency(binding.domain))
            dependencies.append(f"role:{binding.role_name}")
        return dependencies


class UserGroupList(BaseList[UserGroup]):
    """Paginated user group resources."""
