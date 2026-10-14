# Copyright 2024 Rapyuta Robotics
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

"""Resource validation models for user."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject

# Type aliases for permissions
ActionMap = dict[str, list[str]]
ResourceMap = dict[str, ActionMap]


class UserPermissions(SDKModel):
    """User permissions model."""

    organization: ResourceMap | None = Field(default=None)
    projects: dict[str, ResourceMap] | None = Field(default=None)
    groups: dict[str, ResourceMap] | None = Field(default=None)


class UserOrganization(SDKModel):
    """User organization model."""

    guid: str | None = None
    name: str | None = None
    creator: str | None = None
    short_guid: str | None = Field(alias="shortGUID")
    role_names: list[str] | None = Field(alias="roleNames")

    @model_validator(mode="after")
    def ensure_name_or_guid(self) -> UserOrganization:
        """Require a resource name or GUID."""
        if self.name is None and self.guid is None:
            message = "either 'name' or 'guid' should be specified"
            raise ValueError(message)

        return self


class UserProject(SDKModel):
    """User project model."""

    guid: str | None = None
    name: str | None = None
    creator: str | None = None
    organization_creator_guid: str | None = Field(alias="organizationCreator")
    organization_guid: str | None = Field(alias="organizationGUID")
    role_names: list[str] | None = Field(alias="roleNames")

    @model_validator(mode="after")
    def ensure_name_or_guid(self) -> UserProject:
        """Require a resource name or GUID."""
        if self.name is None and self.guid is None:
            message = "either 'name' or 'guid' should be specified"
            raise ValueError(message)

        return self


class UserUserGroup(SDKModel):
    """User group model."""

    guid: str | None = None
    name: str | None = None
    creator: str | None = None
    organization_creator_guid: str | None = Field(
        default=None, alias="organizationCreatorGUID"
    )
    organization_guid: str | None = Field(default=None, alias="organizationGUID")
    role_names: list[str] = Field(alias="roleNames")

    @model_validator(mode="after")
    def ensure_name_or_guid(self) -> UserUserGroup:
        """Require a resource name or GUID."""
        if self.name is None and self.guid is None:
            message = "either 'name' or 'guid' should be specified"
            raise ValueError(message)

        return self


class UserSpec(SDKModel):
    """User specification model."""

    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    email_id: str | None = Field(default=None, alias="emailID")
    password: str | None = None

    organizations: list[UserOrganization] | None = None
    projects: list[UserProject] | None = None
    user_groups: list[UserUserGroup] | None = Field(default=None, alias="userGroups")


class User(BaseObject):
    """User model."""

    kind: Literal["User", "ServiceAccount"] | None = "User"
    metadata: BaseMetadata
    spec: UserSpec


class UserList(BaseList[User]):
    """List of users using BaseList."""
