"""
Pydantic models for Network resource validation.

This module contains Pydantic models that correspond to the Network JSON schema,
providing validation for Network resources to help users identify missing or
incorrect fields.
"""

from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from rapyuta_io_sdk_v2.models.utils import (
    Architecture,
    BaseList,
    BaseMetadata,
    RestartPolicy,
    Runtime,
)


class RabbitMQCreds(BaseModel):
    defaultUser: str
    defaultPassword: str


class ResourceLimits(BaseModel):
    cpu: float = Field(..., multiple_of=0.025)
    memory: int = Field(..., multiple_of=128)


class Depends(BaseModel):
    kind: Literal["Device"] | None = Field(default="Device")
    nameOrGuid: str = Field(validation_alias=AliasChoices("nameOrGuid", "nameOrGUID"))


class DiscoveryServerData(BaseModel):
    serverID: int | None = None
    serverPort: int | None = None


class NetworkSpec(BaseModel):
    type: Literal["routed", "native"]
    rosDistro: Literal["melodic", "kinetic", "noetic", "foxy"]
    runtime: Runtime
    discoveryServer: DiscoveryServerData | None = None
    resourceLimits: ResourceLimits | None = None
    depends: Depends | None = Field(default=None)
    networkInterface: str | None = None
    restartPolicy: RestartPolicy | None = None
    architecture: Architecture | None = None
    rabbitMQCreds: RabbitMQCreds | None = None

    # Needed as sometimes in result json depends comes as empty JSON
    # For e.g., depends: {}
    @field_validator("depends", mode="before")
    @classmethod
    def empty_dict_to_none(cls, v):
        if v == {}:
            return None
        return v


class NetworkStatus(BaseModel):
    phase: str
    status: str
    errorCodes: list[str] | None = None


class Network(BaseModel):
    """Network model."""

    model_config = ConfigDict(extra="forbid")

    apiVersion: str | None = None
    kind: str | None = None
    metadata: BaseMetadata | None = None
    spec: NetworkSpec | None = None
    status: NetworkStatus | None = None


class NetworkList(BaseList[Network]):
    """List of networks using BaseList."""

    pass
