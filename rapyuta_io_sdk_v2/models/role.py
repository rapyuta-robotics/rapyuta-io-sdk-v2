from __future__ import annotations

from typing import ClassVar, Literal

from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject, SDKModel
from rapyuta_io_sdk_v2.resource_operations import Request


class Rule(SDKModel):
    resource: str
    instances: list[str] | None = None
    actions: list[str] | None = None


class RoleSpec(SDKModel):
    description: str | None = None
    rules: list[Rule] | None = None


class Role(BaseObject):
    kind: Literal["Role"] | None = "Role"
    metadata: BaseMetadata
    spec: RoleSpec

    resource_kind: ClassVar[str] = "Role"

    endpoint: ClassVar[str] = "role"

    mutable: ClassVar[bool] = True

    def _update(self):
        return (yield Request("update_role", (self.metadata.name, self)))


class RoleList(BaseList[Role]):
    pass
