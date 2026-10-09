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

from typing import Literal

from pydantic import BaseModel, Field

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    Domain,
    Subject,
    named_resource_dependency,
)


class UserGroupMemberCreate(BaseModel):
    """Subject and explicit roles added to a user group."""

    subject: Subject
    role_names: list[str] | None = Field(default=None, alias="roleNames")


class UserGroupMember(UserGroupMemberCreate):
    """User group member with explicit and inherited roles."""

    implicit_role_names: list[str] | None = Field(
        default=None, alias="implicitRoleNames"
    )


class UserGroupBinding(BaseModel):
    """Role assigned to a user group within a domain."""

    domain: Domain
    role_name: str = Field(alias="roleName")


class UserGroupSpec(BaseModel):
    """Group description, memberships, and authorization bindings."""

    description: str | None = None
    members_count: int | None = Field(default=None, alias="membersCount")
    members: list[UserGroupMember] | None = None
    roles: list[UserGroupBinding] | None = None


class UserGroupSpecCreate(UserGroupSpec):
    """Group creation fields with explicit membership assignments."""

    members: list[UserGroupMemberCreate] | None = None


class UserGroup(BaseObject):
    """Named user group and its membership and authorization settings."""

    kind: Literal["UserGroup"] | None = "UserGroup"
    metadata: BaseMetadata
    spec: UserGroupSpec


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
