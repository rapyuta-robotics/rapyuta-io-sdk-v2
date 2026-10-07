from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject, SDKModel


if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.context import RequestContext


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

    mutable: ClassVar[bool] = True

    def create(self, client: Client, *, context: RequestContext | None = None):
        return client.create_role(self, context=context)

    def update(self, client: Client, *, context: RequestContext | None = None):
        return client.update_role(self.metadata.name, self, context=context)

    async def create_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.create_role(self, context=context)

    async def update_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.update_role(self.metadata.name, self, context=context)

    def _delete(self, client: Client, *, context: RequestContext | None = None) -> None:
        client.delete_role(self.metadata.name, context=context)

    async def _delete_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> None:
        await client.delete_role(self.metadata.name, context=context)


class RoleList(BaseList[Role]):
    pass
