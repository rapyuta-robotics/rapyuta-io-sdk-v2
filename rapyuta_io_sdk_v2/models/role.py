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

"""Resource validation models for role."""

from typing import Literal

from pydantic import BaseModel

from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject


class Rule(BaseModel):
    """Resources and actions permitted by a role."""

    resource: str
    instances: list[str] | None = None
    actions: list[str] | None = None


class RoleSpec(BaseModel):
    """Role description and authorization rules."""

    description: str | None = None
    rules: list[Rule] | None = None


class Role(BaseObject):
    """Named collection of authorization rules."""

    kind: Literal["Role"] | None = "Role"
    metadata: BaseMetadata
    spec: RoleSpec


class RoleList(BaseList[Role]):
    """Paginated role resources."""
