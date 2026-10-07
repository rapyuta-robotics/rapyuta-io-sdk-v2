from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field

from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError
from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    Domain,
    SDKModel,
    Subject,
    resource_key,
)
from rapyuta_io_sdk_v2.resource_operations import ApplyError


if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.context import RequestContext


class UserGroupMemberCreate(SDKModel):
    subject: Subject
    role_names: list[str] | None = Field(default=None, alias="roleNames")


class UserGroupMember(UserGroupMemberCreate):
    implicit_role_names: list[str] | None = Field(default=None, alias="implicitRoleNames")


class UserGroupBinding(SDKModel):
    domain: Domain
    role_name: str = Field(alias="roleName")


class UserGroupSpec(SDKModel):
    description: str | None = None
    members_count: int | None = Field(default=None, alias="membersCount")
    members: list[UserGroupMember] | None = None
    roles: list[UserGroupBinding] | None = None


class UserGroupSpecCreate(UserGroupSpec):
    members: list[UserGroupMemberCreate] | None = None


class UserGroup(BaseObject):
    kind: Literal["UserGroup"] | None = "UserGroup"
    metadata: BaseMetadata
    spec: UserGroupSpec

    resource_kind: ClassVar[str] = "UserGroup"

    can_apply: ClassVar[bool] = False

    mutable: ClassVar[bool] = True

    def dependencies(self) -> list[str]:
        dependencies: list[str] = []

        # Process members and their roles
        if self.spec.members is not None:
            for member in self.spec.members:
                if member.subject.kind is not None and member.subject.name is not None:
                    subject = resource_key(
                        member.subject.kind.lower(), member.subject.name
                    )
                    dependencies.append(subject)

                if member.role_names is not None:
                    for role in member.role_names:
                        dependencies.append(resource_key("role", role))

        # Process group roles and their domains
        if self.spec.roles is not None:
            for group_role in self.spec.roles:
                if (
                    group_role.domain.kind is not None
                    and group_role.domain.name is not None
                ):
                    domain = resource_key(
                        group_role.domain.kind.lower(), group_role.domain.name
                    )
                    dependencies.append(domain)

                dependencies.append(resource_key("role", group_role.role_name))

        return list(dict.fromkeys(dependencies))

    def _lookup(self, client: Client, *, context: RequestContext | None = None) -> str:
        if self.metadata.guid:
            return self.metadata.guid
        matches = []
        cursor = 0
        seen = set()
        while True:
            page = client.list_user_groups(
                name=self.metadata.name, cont=cursor, context=context
            )
            matches.extend(
                resource
                for resource in page.items
                if resource.metadata.name == self.metadata.name
            )
            next_cursor = page.metadata.continue_ if page.metadata is not None else None
            if next_cursor is None or not page.items or len(page.items) < 50:
                break
            if next_cursor in seen:
                raise ApplyError(
                    f"Repeated continuation token while resolving {self.identity}"
                )
            seen.add(next_cursor)
            cursor = next_cursor
        if len(matches) > 1:
            raise ApplyError(f"Ambiguous group name {self.metadata.name}")
        if not matches or not matches[0].metadata.guid:
            raise HttpNotFoundError(f"Group {self.metadata.name} not found")
        return matches[0].metadata.guid

    def _delete(self, client: Client, *, context: RequestContext | None = None) -> None:
        guid = self._lookup(client, context=context)
        client.delete_user_group(self.metadata.name, guid, context=context)

    async def _lookup_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> str:
        if self.metadata.guid:
            return self.metadata.guid
        matches = []
        cursor = 0
        seen = set()
        while True:
            page = await client.list_user_groups(
                name=self.metadata.name, cont=cursor, context=context
            )
            matches.extend(
                resource
                for resource in page.items
                if resource.metadata.name == self.metadata.name
            )
            next_cursor = page.metadata.continue_ if page.metadata is not None else None
            if next_cursor is None or not page.items or len(page.items) < 50:
                break
            if next_cursor in seen:
                raise ApplyError(
                    f"Repeated continuation token while resolving {self.identity}"
                )
            seen.add(next_cursor)
            cursor = next_cursor
        if len(matches) > 1:
            raise ApplyError(f"Ambiguous group name {self.metadata.name}")
        if not matches or not matches[0].metadata.guid:
            raise HttpNotFoundError(f"Group {self.metadata.name} not found")
        return matches[0].metadata.guid

    async def _delete_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> None:
        guid = await self._lookup_async(client, context=context)
        await client.delete_user_group(self.metadata.name, guid, context=context)


class UserGroupCreate(UserGroup):
    can_apply: ClassVar[bool] = True

    spec: UserGroupSpecCreate

    def create(self, client: Client, *, context: RequestContext | None = None):
        return client.create_user_group(self, context=context)

    async def create_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.create_user_group(self, context=context)

    @classmethod
    def model_for_operation(cls, operation: str):
        if operation == "delete" and cls is UserGroupCreate:
            return UserGroup
        return cls

    def update(self, client: Client, *, context: RequestContext | None = None):
        guid = self._lookup(client, context=context)
        body = self.model_copy(deep=True)
        body.metadata.guid = guid
        return client.update_user_group(self.metadata.name, guid, body, context=context)

    async def update_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        guid = await self._lookup_async(client, context=context)
        body = self.model_copy(deep=True)
        body.metadata.guid = guid
        return await client.update_user_group(
            self.metadata.name, guid, body, context=context
        )


class UserGroupList(BaseList[UserGroup]):
    pass
