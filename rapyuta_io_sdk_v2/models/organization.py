from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field

from rapyuta_io_sdk_v2.models.utils import SDKModel
from rapyuta_io_sdk_v2.resource_operations import ApplyError, Outcome, Request

from .utils import BaseMetadata, BaseObject, Subject


class OrganizationMember(SDKModel):
    subject: Subject
    role_names: list[str] = Field(alias="roleNames")


class OrganizationSpec(SDKModel):
    members: list[OrganizationMember]


class Organization(BaseObject):
    kind: Literal["Organization"] | None = "Organization"
    metadata: BaseMetadata
    spec: OrganizationSpec

    resource_kind: ClassVar[str] = "Organization"

    endpoint: ClassVar[str] = "organization"

    can_delete: ClassVar[bool] = False

    def validate_operation(self, operation: str) -> None:
        super().validate_operation(operation)
        if not self.metadata.guid:
            raise ApplyError("Organization apply requires metadata.guid")

    def workflow(self, operation: str, attempts: int, interval: float):
        response = yield Request(
            "update_organization",
            (self,),
            {"organization_guid": self.metadata.guid},
        )
        return Outcome.UPDATED, response
