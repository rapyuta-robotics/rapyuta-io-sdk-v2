from typing import Literal

from pydantic import BaseModel, Field

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    Domain,
    Subject,
)


class UserGroupMember(BaseModel):
    subject: Subject
    role_names: list[str] = Field(alias="roleNames")


class UserGroupBinding(BaseModel):
    domain: Domain
    role_name: str = Field(alias="roleName")


class UserGroupSpec(BaseModel):
    description: str | None = None
    members_count: int | None = Field(default=None, alias="membersCount")
    members: list[UserGroupMember] | None = None
    roles: list[UserGroupBinding] | None = None


class UserGroup(BaseObject):
    kind: Literal["UserGroup"] | None = "UserGroup"
    metadata: BaseMetadata
    spec: UserGroupSpec


class UserGroupList(BaseList[UserGroup]):
    pass
