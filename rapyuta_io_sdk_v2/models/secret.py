"""
Pydantic models for Secret resource validation.

This module contains Pydantic models that correspond to the Secret JSON schema,
providing validation for Secret resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field, model_validator

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    DeviceDepends,
    Runtime,
    SDKModel,
    resource_key,
)


if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.context import RequestContext


class DockerSpec(SDKModel):
    registry: str = Field(
        default="https://index.docker.io/v1/", description="Docker registry URL"
    )
    username: str = Field(description="Username for docker registry authentication")
    email: str = Field(description="Email for docker registry authentication")


class DockerSpecCreate(DockerSpec):
    password: str = Field(description="Password for docker registry authentication")


SecretType = Literal["Docker", "Opaque"]


class SecretSpec(SDKModel):
    """Specification for Secret resource."""

    type: SecretType = Field(
        description="Type of the secret: Docker or Opaque",
    )
    docker: DockerSpec | None = Field(
        default=None,
        description="Docker registry configuration when type is Docker",
    )
    data: dict[str, str] | None = Field(
        default=None,
        description="Arbitrary key-value data for Opaque secrets",
    )
    secret_keys: list[str] | None = Field(
        default=None,
        alias="secretKeys",
        description="List of keys present in the secret (read-only, returned by server)",
    )
    runtime: Runtime | None = None
    depends: DeviceDepends | None = None


class SecretSpecCreate(SDKModel):
    type: SecretType = Field(
        description="Type of the secret: Docker or Opaque",
    )
    docker: DockerSpecCreate | None = None
    data: dict[str, str] | None = Field(
        default=None,
        description="Arbitrary key-value data for Opaque secrets",
    )
    runtime: Runtime | None = None
    depends: DeviceDepends | None = None


class Secret(BaseObject):
    """Secret model."""

    kind: Literal["Secret"] | None = "Secret"
    metadata: BaseMetadata
    spec: SecretSpec = Field(description="Specification for the Secret resource")

    resource_kind: ClassVar[str] = "Secret"

    can_apply: ClassVar[bool] = False

    mutable: ClassVar[bool] = True

    def _delete(self, client: Client, *, context: RequestContext | None = None) -> None:
        client.delete_secret(self.metadata.name, context=context)

    async def _delete_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> None:
        await client.delete_secret(self.metadata.name, context=context)

    def dependencies(self) -> list[str]:
        runtime = self.spec.runtime

        if not runtime or runtime == "cloud":
            return []

        if self.spec.depends is not None:
            device_name = self.spec.depends.name_or_guid
            return [resource_key("device", device_name)]

        return []


class SecretCreate(Secret):
    can_apply: ClassVar[bool] = True

    spec: SecretSpecCreate

    @model_validator(mode="after")
    def validate_create_fields(self):
        spec = self.spec
        if spec.type == "Docker":
            if spec.docker is None:
                raise ValueError(
                    "'spec.docker' is required when creating a Docker secret"
                )
        elif spec.type == "Opaque":
            if not spec.data:
                raise ValueError("'spec.data' is required when creating an Opaque secret")
        return self

    def create(self, client: Client, *, context: RequestContext | None = None):
        return client.create_secret(self, context=context)

    def update(self, client: Client, *, context: RequestContext | None = None):
        return client.update_secret(self.metadata.name, self, context=context)

    async def create_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.create_secret(self, context=context)

    async def update_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.update_secret(self.metadata.name, self, context=context)

    @classmethod
    def model_for_operation(cls, operation: str):
        if operation == "delete" and cls is SecretCreate:
            return Secret
        return cls


class SecretList(BaseList[Secret]):
    """List of secrets using BaseList."""

    pass
