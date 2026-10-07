from __future__ import annotations

from typing import Literal

from pydantic import Field

from .utils import BaseMetadata, BaseObject, Subject
from rapyuta_io_sdk_v2.models.utils import SDKModel


class OrganizationMember(SDKModel):
    subject: Subject
    role_names: list[str] = Field(alias="roleNames")


class OrganizationSpec(SDKModel):
    members: list[OrganizationMember]


class Organization(BaseObject):
    kind: Literal["Organization"] | None = "Organization"
    metadata: BaseMetadata
    spec: OrganizationSpec
