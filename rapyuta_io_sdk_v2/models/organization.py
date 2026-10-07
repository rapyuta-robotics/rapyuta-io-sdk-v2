from __future__ import annotations

from rapyuta_io_sdk_v2.resource_operations import Outcome

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field

from rapyuta_io_sdk_v2.models.utils import SDKModel
from rapyuta_io_sdk_v2.resource_operations import ApplyError

from .utils import BaseMetadata, BaseObject, Subject


if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.context import RequestContext


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

    can_delete: ClassVar[bool] = False

    def validate_operation(self, operation: str) -> None:
        super().validate_operation(operation)
        if not self.metadata.guid:
            raise ApplyError("Organization apply requires metadata.guid")

    def update(self, client: Client, *, context: RequestContext | None = None):
        return client.update_organization(
            self, organization_guid=self.metadata.guid, context=context
        )

    def _apply(
        self,
        client: Client,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None,
    ):
        return Outcome.UPDATED, self.update(client, context=context)

    async def update_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.update_organization(
            self, organization_guid=self.metadata.guid, context=context
        )

    async def _apply_async(
        self,
        client: AsyncClient,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None,
    ):
        return Outcome.UPDATED, await self.update_async(client, context=context)
