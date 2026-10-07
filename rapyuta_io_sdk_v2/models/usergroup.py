from __future__ import annotations

from typing import Literal

from pydantic import Field

from rapyuta_io_sdk_v2.models.utils import (
    resource_key,
    SDKModel,
    BaseList,
    BaseMetadata,
    BaseObject,
    Domain,
    Subject,
)


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


class UserGroupCreate(UserGroup):
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
