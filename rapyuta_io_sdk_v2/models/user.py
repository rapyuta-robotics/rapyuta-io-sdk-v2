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

from typing import Literal, Self

from pydantic import AliasChoices, BaseModel, Field, model_validator

from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject


class UserOrganization(BaseModel):
    """User organization model."""

    guid: str | None = None
    name: str | None = None
    creator: str | None = None
    short_guid: str | None = Field(alias="shortGUID")
    role_names: list[str] | None = Field(alias="roleNames")

    @model_validator(mode="after")
    def ensure_name_or_guid(self) -> Self:
        if self.name is None and self.guid is None:
            raise ValueError("either 'name' or 'guid' should be specified")

        return self


class UserProject(BaseModel):
    """User project model."""

    guid: str | None = None
    name: str | None = None
    creator: str | None = None
    organization_creator_guid: str | None = Field(
        validation_alias=AliasChoices("organizationCreator")
    )
    organization_guid: str | None = Field(alias="organizationGUID")
    role_names: list[str] | None = Field(alias="roleNames")

    @model_validator(mode="after")
    def ensure_name_or_guid(self) -> Self:
        if self.name is None and self.guid is None:
            raise ValueError("either 'name' or 'guid' should be specified")

        return self


class UserUserGroup(BaseModel):
    """User group model."""

    guid: str | None = None
    name: str | None = None
    creator: str | None = None
    organization_creator_guid: str | None = Field(default=None, alias="organizationCreatorGUID")
    organization_guid: str | None = Field(default=None, alias="organizationGUID")
    role_names: list[str] = Field(alias="roleNames")

    @model_validator(mode="after")
    def ensure_name_or_guid(self) -> Self:
        if self.name is None and self.guid is None:
            raise ValueError("either 'name' or 'guid' should be specified")

        return self


class UserSpec(BaseModel):
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

    kind: Literal["User"] | None = "User"
    metadata: BaseMetadata
    spec: UserSpec


class UserList(BaseList[User]):
    """List of users using BaseList."""

    pass
