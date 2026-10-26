from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    Domain,
    Subject,
)


class RoleBindingMetadata(BaseMetadata):
    name: None = Field(default=None, exclude=True)


class RoleRef(BaseModel):
    kind: Literal["Role"] = "Role"
    name: str | None = None
    guid: str | None = None

    @model_validator(mode="after")
    def ensure_name_or_guid(self):
        if self.name is None and self.guid is None:
            raise ValueError("either 'name' or 'guid' should be specified")

        return self


class RoleBindingSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role_ref: RoleRef = Field(alias="roleRef")
    domain: Domain
    subject: Subject
    # The binding is time-bound when not_after is set. Older servers ignore both.
    not_before: datetime | None = Field(default=None, alias="notBefore")
    not_after: datetime | None = Field(default=None, alias="notAfter")

    @field_validator("not_before", "not_after")
    @classmethod
    def check_window_timezone(cls, v):
        if v is not None and v.tzinfo is None:
            raise ValueError("notBefore and notAfter must carry a time zone")
        return v


class RoleBinding(BaseObject):
    kind: Literal["RoleBinding"] | None = "RoleBinding"
    metadata: RoleBindingMetadata
    spec: RoleBindingSpec

    def list_dependencies(self) -> list[str] | None:
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
    new_bindings: list[RoleBinding] = Field(default_factory=list, alias="newBindings")
    old_bindings: list[RoleBinding | None] = Field(
        default_factory=list, alias="oldBindings"
    )


class RoleBindingList(BaseList[RoleBinding]):
    pass
