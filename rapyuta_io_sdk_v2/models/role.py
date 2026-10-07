from __future__ import annotations

from typing import Literal

from rapyuta_io_sdk_v2.models.utils import SDKModel, BaseList, BaseMetadata, BaseObject


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


class RoleList(BaseList[Role]):
    pass
