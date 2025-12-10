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
    role_ref: RoleRef = Field(alias="roleRef")
    domain: Domain
    subject: Subject


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
    new_bindings: list[RoleBinding] = Field(alias="newBindings")
    old_bindings: list[RoleBinding | None] = Field(alias="oldBindings")


class RoleBindingList(BaseList[RoleBinding]):
    pass
