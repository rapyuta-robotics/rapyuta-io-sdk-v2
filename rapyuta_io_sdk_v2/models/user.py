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

from pydantic import BaseModel, Field
from rapyuta_io_sdk_v2.models.utils import BaseMetadata, BaseList


class UserOrganization(BaseModel):
    """User organization model."""

    creator: str | None = None
    guid: str | None = None
    name: str | None = None
    shortGUID: str | None = Field(None, alias="shortGUID")


class UserProject(BaseModel):
    """User project model."""

    creator: str | None = None
    guid: str | None = None
    name: str | None = None
    organizationCreatorGUID: str | None = None
    organizationGUID: str | None = None


class UserGroup(BaseModel):
    """User group model."""

    creator: str | None = None
    guid: str | None = None
    name: str | None = None
    organizationCreatorGUID: str | None = None
    organizationGUID: str | None = None


class UserSpec(BaseModel):
    """User specification model."""

    emailID: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    organizations: list[UserOrganization] | None = None
    password: str | None = None
    projects: list[UserProject] | None = None
    userGroupAdmins: list[UserGroup] | None = None
    userGroupsMembers: list[UserGroup] | None = None


class User(BaseModel):
    """User model."""

    apiVersion: str | None = None
    kind: str | None = None
    metadata: BaseMetadata | None = None
    spec: UserSpec | None = None


class UserList(BaseList[User]):
    """List of users using BaseList."""

    pass
    pass
