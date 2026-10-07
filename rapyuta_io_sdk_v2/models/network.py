"""
Pydantic models for Network resource validation.

This module contains Pydantic models that correspond to the Network JSON schema,
providing validation for Network resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, field_validator, AliasChoices

from rapyuta_io_sdk_v2.models.utils import (
    resource_key,
    SDKModel,
    Architecture,
    BaseList,
    BaseMetadata,
    RestartPolicy,
    Runtime,
)


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


class Network(SDKModel):
    """Network model."""

    model_config = ConfigDict(extra="forbid")

    api_version: str | None = Field(default=None, alias="apiVersion")
    kind: str | None = None
    metadata: BaseMetadata | None = None
    spec: NetworkSpec | None = None
    status: NetworkStatus | None = None

    def list_dependencies(self) -> list[str]:
        dependencies: list[str] = []

        if self.spec and self.spec.runtime == "device" and self.spec.depends:
            dependencies.append(resource_key("device", self.spec.depends.name_or_guid))

        if dependencies == []:
            return None

        return dependencies


class NetworkList(BaseList[Network]):
    """List of networks using BaseList."""

    pass
