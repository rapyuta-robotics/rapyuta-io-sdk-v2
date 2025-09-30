from typing import Literal

from pydantic import BaseModel

from .utils import BaseMetadata, BaseObject, Subject

# Define allowed roles
RoleType = Literal["admin", "viewer"]


class OrganizationMember(BaseModel):
    subject: Subject
    roleNames: list[str]


class OrganizationSpec(BaseModel):
    members: list[OrganizationMember]


class Organization(BaseObject):
    kind: Literal["Organization"] | None = "Organization"
    metadata: BaseMetadata
    spec: OrganizationSpec
