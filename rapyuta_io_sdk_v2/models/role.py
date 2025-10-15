from typing import Literal

from pydantic import BaseModel

from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject


class Rule(BaseModel):
    resource: str
    instances: list[str] | None = None
    actions: list[str] | None = None


class RoleSpec(BaseModel):
    description: str | None = None
    rules: list[Rule] | None = None


class Role(BaseObject):
    kind: Literal["Role"] | None = "Role"
    metadata: BaseMetadata
    spec: RoleSpec


class RoleList(BaseList[Role]):
    pass
