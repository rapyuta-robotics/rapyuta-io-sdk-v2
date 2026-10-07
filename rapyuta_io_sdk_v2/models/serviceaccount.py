"""
Pydantic models for ServiceAccount resource validation.

This module mirrors the Go `ServiceAccount` and related types from the
`package extensions` snippet provided by the user.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field, field_validator

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    Domain,
    SDKModel,
    resource_key,
)


if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.context import RequestContext


class ServiceAccountBinding(SDKModel):
    domain: Domain
    role_names: list[str] = Field(default_factory=list, alias="roleNames")


class ServiceAccountSpec(SDKModel):
    description: str | None = None
    roles: list[ServiceAccountBinding] | None = None


class ServiceAccount(BaseObject):
    """ServiceAccount model."""

    kind: Literal["ServiceAccount", "serviceaccount"] | None = "ServiceAccount"
    metadata: BaseMetadata
    spec: ServiceAccountSpec | None = None

    def dependencies(self) -> list[str]:
        dependencies: list[str] = []

        # Process service account roles and their domains
        if self.spec and self.spec.roles is not None:
            for role_binding in self.spec.roles:
                # Add domain dependency
                if (
                    role_binding.domain.kind is not None
                    and role_binding.domain.name is not None
                ):
                    domain = resource_key(
                        role_binding.domain.kind.lower(), role_binding.domain.name
                    )
                    dependencies.append(domain)

                # Add role dependencies
                if role_binding.role_names is not None:
                    for role in role_binding.role_names:
                        dependencies.append(resource_key("role", role))

        return list(dict.fromkeys(dependencies))

    resource_kind: ClassVar[str] = "ServiceAccount"

    mutable: ClassVar[bool] = True

    def create(self, client: Client, *, context: RequestContext | None = None):
        return client.create_service_account(self, context=context)

    def update(self, client: Client, *, context: RequestContext | None = None):
        return client.update_service_account(self, self.metadata.name, context=context)

    async def create_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.create_service_account(self, context=context)

    async def update_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.update_service_account(
            self, self.metadata.name, context=context
        )

    def _delete(self, client: Client, *, context: RequestContext | None = None) -> None:
        client.delete_service_account(self.metadata.name, context=context)

    async def _delete_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> None:
        await client.delete_service_account(self.metadata.name, context=context)


class ServiceAccountList(BaseList[ServiceAccount]):
    """List of service accounts using BaseList."""

    pass


class ServiceAccountToken(SDKModel):
    owner: str | None = None
    expiry_at: datetime | None = Field(default=None, alias="expiry_at")

    @field_validator("expiry_at")
    @classmethod
    def check_expiry_at_iso8601(cls, v):
        if v is not None and v.tzinfo is None:
            raise ValueError("expiry_at must be an ISO8601 datetime with timezone info")
        return v


class ServiceAccountTokenInfo(SDKModel):
    id: int | None = None
    token: str | None = None
    expiry_at: datetime | None = Field(default=None, alias="expiry_at")

    @field_validator("expiry_at")
    @classmethod
    def check_expiry_at_iso8601(cls, v):
        if v is not None and v.tzinfo is None:
            raise ValueError("expiry_at must be an ISO8601 datetime with timezone info")
        return v


class ServiceAccountTokenList(BaseList[ServiceAccountTokenInfo]):
    """List of service account tokens."""

    pass
