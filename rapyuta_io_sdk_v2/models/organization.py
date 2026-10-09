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

from typing import Literal

from pydantic import Field

from rapyuta_io_sdk_v2.models.base import SDKModel

from .utils import BaseMetadata, BaseObject, Subject


class OrganizationMember(SDKModel):
    """Organization subject and its assigned roles."""

    subject: Subject
    role_names: list[str] = Field(alias="roleNames")


class OrganizationSpec(SDKModel):
    """Members authorized within an organization."""

    members: list[OrganizationMember]


class Organization(BaseObject):
    """Organization identity and membership manifest."""

    kind: Literal["Organization"] | None = "Organization"
    metadata: BaseMetadata
    spec: OrganizationSpec
