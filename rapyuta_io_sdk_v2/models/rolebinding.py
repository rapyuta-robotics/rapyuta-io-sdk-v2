from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, RootModel, model_validator

from rapyuta_io_sdk_v2.models.utils import (
    resource_key,
    SDKModel,
    BaseList,
    BaseMetadata,
    BaseObject,
    Domain,
    Subject,
)


class RoleBindingMetadata(BaseMetadata):
    name: None = Field(default=None, exclude=True)


class RoleRef(SDKModel):
    kind: Literal["Role"] = "Role"
    name: str | None = None
    guid: str | None = None

    @model_validator(mode="after")
    def ensure_name_or_guid(self):
        if self.name is None and self.guid is None:
            raise ValueError("either 'name' or 'guid' should be specified")

        return self


class RoleBindingSpec(SDKModel):
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
            dependencies.append(resource_key("role", self.spec.role_ref.name))

        # Add subject dependency
        if self.spec.subject.kind is not None and self.spec.subject.name is not None:
            dependencies.append(
                resource_key(self.spec.subject.kind, self.spec.subject.name)
            )

        # Add domain dependency
        if self.spec.domain.kind is not None and self.spec.domain.name is not None:
            dependencies.append(
                resource_key(self.spec.domain.kind, self.spec.domain.name)
            )

        return dependencies


class BulkRoleBindingUpdate(SDKModel):
    new_bindings: list[RoleBinding] = Field(alias="newBindings")
    old_bindings: list[RoleBinding | None] = Field(alias="oldBindings")


class RoleBindingList(BaseList[RoleBinding]):
    pass


class BulkRoleBindingResponse(RootModel[dict[str, Any] | list[Any]]):
    """Bulk result envelope; the server does not guarantee a single binding."""
