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

"""Resource validation models for rolebinding."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    Domain,
    Subject,
)


class RoleBindingMetadata(BaseMetadata):
    """Binding metadata that omits the resource name."""

    name: None = Field(default=None, exclude=True)


class RoleRef(BaseModel):
    """Role identified by name or GUID."""

    kind: Literal["Role"] = "Role"
    name: str | None = None
    guid: str | None = None

    @model_validator(mode="after")
    def ensure_name_or_guid(self) -> RoleRef:
        """Require a resource name or GUID."""
        if self.name is None and self.guid is None:
            message = "either 'name' or 'guid' should be specified"
            raise ValueError(message)

        return self


class RoleBindingSpec(BaseModel):
    """Role granted to a subject within a domain."""

    role_ref: RoleRef = Field(alias="roleRef")
    domain: Domain
    subject: Subject


class RoleBinding(BaseObject):
    """Authorization grant connecting a role, subject, and domain."""

    kind: Literal["RoleBinding"] | None = "RoleBinding"
    metadata: RoleBindingMetadata
    spec: RoleBindingSpec

    def list_dependencies(self) -> list[str] | None:
        """Return resource dependencies in manifest order."""
        dependencies: list[str] = []

        # Add role dependency
        if self.spec.role_ref.name is not None:
            dependencies.append(f"role:{self.spec.role_ref.name}")

        # Add subject dependency
        if self.spec.subject.kind is not None and self.spec.subject.name is not None:
            dependencies.append(f"{self.spec.subject.kind}:{self.spec.subject.name}")

        # Add domain dependency
        if self.spec.domain.kind is not None and self.spec.domain.name is not None:
            dependencies.append(f"{self.spec.domain.kind}:{self.spec.domain.name}")

        return dependencies


class BulkRoleBindingUpdate(BaseModel):
    """Bindings to add and bindings to replace in one update."""

    new_bindings: list[RoleBinding] = Field(alias="newBindings")
    old_bindings: list[RoleBinding | None] = Field(alias="oldBindings")


class RoleBindingList(BaseList[RoleBinding]):
    """Paginated role binding resources."""
