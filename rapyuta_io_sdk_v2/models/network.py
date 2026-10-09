# Copyright 2026 Rapyuta Robotics
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Pydantic models for Network resource validation.

This module contains Pydantic models that correspond to the Network JSON schema,
providing validation for Network resources to help users identify missing or
incorrect fields.
"""

from typing import Literal

from pydantic import AliasChoices, ConfigDict, Field, field_validator

from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.utils import (
    Architecture,
    BaseList,
    BaseMetadata,
    RestartPolicy,
    Runtime,
)


class RabbitMQCreds(SDKModel):
    """Credentials for the network RabbitMQ instance."""

    default_user: str = Field(alias="defaultUser")
    default_password: str = Field(alias="defaultPassword")


class ResourceLimits(SDKModel):
    """CPU and memory limits for a network service."""

    cpu: float = Field(..., multiple_of=0.025)
    memory: int = Field(..., multiple_of=128)


class Depends(SDKModel):
    """Resource reference identified by name or GUID."""

    kind: Literal["Device"] | None = Field(default="Device")
    name_or_guid: str = Field(
        validation_alias=AliasChoices("nameOrGUID", "nameOrGuid"),
        serialization_alias="nameOrGUID",
    )


class DiscoveryServerData(SDKModel):
    """ROS discovery server identifier and listening port."""

    server_id: int | None = Field(default=None, alias="serverID")
    server_port: int | None = Field(default=None, alias="serverPort")


class NetworkSpec(SDKModel):
    """ROS networking, runtime, discovery, and service configuration."""

    type: Literal["routed", "native"]
    ros_distro: Literal["melodic", "kinetic", "noetic", "foxy"] = Field(
        alias="rosDistro"
    )
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
    def empty_dict_to_none(cls, v: object) -> object:
        """Normalize empty configuration dictionaries to absent values.

        Args:
            v: Field value supplied to the validator.
        """
        if v == {}:
            return None
        return v


class NetworkStatus(SDKModel):
    """Network lifecycle and provisioning errors."""

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
        """Return resource dependencies in manifest order."""
        dependencies: list[str] = []

        if self.spec.runtime == "device":
            dependencies.append(f"device:{self.spec.depends.name_or_guid}")

        if dependencies == []:
            return None

        return dependencies


class NetworkList(BaseList[Network]):
    """List of networks using BaseList."""
