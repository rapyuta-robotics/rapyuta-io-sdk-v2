from __future__ import annotations

from typing import ClassVar, Literal

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
from rapyuta_io_sdk_v2.resource_operations import ApplyError, Request


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

    endpoint: ClassVar[str] = "user_group"

    mutable: ClassVar[bool] = True

    def _lookup(self):
        if self.metadata.guid:
            return self.metadata.guid
        matches = yield from self._named_resources("list_user_groups")
        if not matches or not matches[0].metadata.guid:
            raise HttpNotFoundError(f"Group {self.metadata.name} not found")
        if len(matches) != 1:
            raise ApplyError(f"Ambiguous group name {self.metadata.name}")
        return matches[0].metadata.guid

    def _update(self):
        self.metadata.guid = yield from self._lookup()
        return (
            yield Request(
                "update_user_group",
                (
                    self.metadata.name,
                    self.metadata.guid,
                    self,
                ),
            )
        )

    def _delete(self):
        guid = yield from self._lookup()
        yield Request("delete_user_group", (self.metadata.name, guid))


class UserGroupCreate(UserGroup):
    can_apply: ClassVar[bool] = True

    spec: UserGroupSpecCreate

    def list_dependencies(self) -> list[str] | None:
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

        return dependencies


class UserGroupList(BaseList[UserGroup]):
    pass
