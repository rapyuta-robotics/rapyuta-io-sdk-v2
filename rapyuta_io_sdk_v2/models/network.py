"""
Pydantic models for Network resource validation.

This module contains Pydantic models that correspond to the Network JSON schema,
providing validation for Network resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

import asyncio
import time

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import AliasChoices, ConfigDict, Field, field_validator

from rapyuta_io_sdk_v2.models.utils import (
    Architecture,
    BaseList,
    BaseMetadata,
    RestartPolicy,
    Runtime,
    SDKModel,
    resource_key,
)
from rapyuta_io_sdk_v2.resource_operations import ReadinessError

from .resource import ResourceModel


if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.context import RequestContext


class RabbitMQCreds(SDKModel):
    default_user: str = Field(alias="defaultUser")
    default_password: str = Field(alias="defaultPassword")


class ResourceLimits(SDKModel):
    cpu: float = Field(..., multiple_of=0.025)
    memory: int = Field(..., multiple_of=128)


class Depends(SDKModel):
    kind: Literal["Device"] | None = Field(default="Device")
    name_or_guid: str = Field(
        validation_alias=AliasChoices("nameOrGUID", "nameOrGuid"),
        serialization_alias="nameOrGUID",
    )


class DiscoveryServerData(SDKModel):
    server_id: int | None = Field(default=None, alias="serverID")
    server_port: int | None = Field(default=None, alias="serverPort")


class NetworkSpec(SDKModel):
    type: Literal["routed", "native"]
    ros_distro: Literal["melodic", "kinetic", "noetic", "foxy"] = Field(alias="rosDistro")
    runtime: Runtime
    discovery_server: DiscoveryServerData | None = Field(
        default=None, alias="discoveryServer"
    )
    resource_limits: ResourceLimits | None = Field(default=None, alias="resourceLimits")
    depends: Depends | None = Field(default=None)
    network_interface: str | None = Field(default=None, alias="networkInterface")
    restart_policy: RestartPolicy | None = Field(default=None, alias="restartPolicy")
    architecture: Architecture | None = None
    rabbit_mq_creds: RabbitMQCreds | None = Field(default=None, alias="rabbitMQCreds")

    # Needed as sometimes in result json depends comes as empty JSON
    # For e.g., depends: {}
    @field_validator("depends", mode="before")
    @classmethod
    def empty_dict_to_none(cls, v):
        if v == {}:
            return None
        return v


class NetworkStatus(SDKModel):
    phase: str
    status: str
    error_codes: list[str] | None = Field(default=None, alias="errorCodes")


class Network(ResourceModel):
    """Network model."""

    model_config = ConfigDict(extra="forbid")

    api_version: str | None = Field(default=None, alias="apiVersion")
    kind: str | None = None
    metadata: BaseMetadata | None = None
    spec: NetworkSpec | None = None
    status: NetworkStatus | None = None

    def dependencies(self) -> list[str]:
        dependencies: list[str] = []

        if self.spec and self.spec.runtime == "device" and self.spec.depends:
            dependencies.append(resource_key("device", self.spec.depends.name_or_guid))

        return dependencies

    resource_kind: ClassVar[str] = "Network"

    def create(self, client: Client, *, context: RequestContext | None = None):
        return client.create_network(self, context=context)

    async def create_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.create_network(self, context=context)

    def _delete(self, client: Client, *, context: RequestContext | None = None) -> None:
        client.delete_network(self.metadata.name, context=context)

    async def _delete_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> None:
        await client.delete_network(self.metadata.name, context=context)

    def wait(
        self,
        client: Client,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None = None,
    ) -> None:
        for attempt in range(attempts):
            resource = client.get_network(self.metadata.name, context=context)
            phase = resource.status.phase if resource.status is not None else None
            if phase == "Succeeded":
                return
            if phase in ("Stopped", "FailedToStart", "FailedToUpdate"):
                raise ReadinessError(f"{self.identity} entered {phase}")
            if attempt + 1 < attempts:
                time.sleep(interval)
        raise ReadinessError(f"{self.identity} readiness timed out")

    async def wait_async(
        self,
        client: AsyncClient,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None = None,
    ) -> None:
        for attempt in range(attempts):
            resource = await client.get_network(self.metadata.name, context=context)
            phase = resource.status.phase if resource.status is not None else None
            if phase == "Succeeded":
                return
            if phase in ("Stopped", "FailedToStart", "FailedToUpdate"):
                raise ReadinessError(f"{self.identity} entered {phase}")
            if attempt + 1 < attempts:
                await asyncio.sleep(interval)
        raise ReadinessError(f"{self.identity} readiness timed out")


class NetworkList(BaseList[Network]):
    """List of networks using BaseList."""

    pass
