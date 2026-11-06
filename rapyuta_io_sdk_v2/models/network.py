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
# Lifecycle helper imports remain local to keep model modules independent.

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal, cast

from pydantic import AliasChoices, ConfigDict, Field, field_validator

from rapyuta_io_sdk_v2.models.applier import (
    DependencyReference,
    ResourceCapabilities,
    ResourceContext,
    ResourceReference,
    ResourceScope,
)
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.resource import ResourceMethods
from rapyuta_io_sdk_v2.models.utils import (
    Architecture,
    BaseList,
    BaseMetadata,
    RestartPolicy,
    Runtime,
)

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client


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


class Network(ResourceMethods, SDKModel):
    """Network model."""

    KIND: ClassVar[str] = "Network"
    CAPABILITIES: ClassVar[ResourceCapabilities] = ResourceCapabilities(
        create=True,
        update=False,
        delete=True,
        apply_policy="create_or_exists",
        readiness_kind="network",
    )

    model_config = ConfigDict(extra="forbid")

    api_version: str | None = Field(default=None, alias="apiVersion")
    kind: str | None = None
    metadata: BaseMetadata | None = None
    spec: NetworkSpec | None = None
    status: NetworkStatus | None = None

    def readiness_state(self) -> tuple[str | None, bool, bool]:
        """Return the observed state, readiness, and terminal failure flags."""
        status = self.status
        if status is None:
            return None, False, False
        state = status.phase or status.status
        terminal = (
            status.status in {"Error", "Stopped"}
            or status.phase in {"Stopped", "FailedToStart", "FailedToUpdate"}
            or "DEP_E153" in (status.error_codes or [])
        )
        return state, status.phase == "Succeeded", terminal

    def list_dependencies(self) -> list[str]:
        """Return resource dependencies in manifest order."""
        dependencies: list[str] = []

        if self.spec.runtime == "device":
            dependencies.append(f"device:{self.spec.depends.name_or_guid}")

        if dependencies == []:
            return None

        return dependencies

    def resource_dependencies(
        self, *, scope: ResourceScope | None = None
    ) -> tuple[DependencyReference, ...]:
        """Declare a Device prerequisite only for explicit device runtime."""
        del scope
        if (
            self.spec is None
            or self.spec.runtime != "device"
            or self.spec.depends is None
        ):
            return ()
        value = self.spec.depends.name_or_guid
        return (
            DependencyReference(
                reference=ResourceReference(kind="device", name=value, guid=value)
            ),
        )

    def create_object(self, client: Client, *, context: ResourceContext) -> Network:
        """Create a Network through the typed SDK operation."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write,
            scoped_context,
            scoped_copy,
        )

        context = scoped_context(self, context)
        payload = scoped_copy(self, context)
        return record_write(
            context,
            "created",
            lambda: client.create_network(payload, **project_options(context)),
        )

    async def create_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> Network:
        """Create a Network through the native asynchronous SDK operation."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write_async,
            scoped_context,
            scoped_copy,
        )

        context = scoped_context(self, context)
        payload = scoped_copy(self, context)
        return await record_write_async(
            context,
            "created",
            lambda: client.create_network(payload, **project_options(context)),
        )

    def _delete_object(self, client: Client, *, context: ResourceContext) -> None:
        """Delete this Network by its scoped name."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write,
        )

        metadata = cast("BaseMetadata", self.metadata)
        record_write(
            context,
            "deleted",
            lambda: client.delete_network(metadata.name, **project_options(context)),
        )

    async def _delete_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> None:
        """Delete this Network through the native async client."""
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            project_options,
            record_write_async,
        )

        metadata = cast("BaseMetadata", self.metadata)
        await record_write_async(
            context,
            "deleted",
            lambda: client.delete_network(metadata.name, **project_options(context)),
        )


class NetworkList(BaseList[Network]):
    """List of networks using BaseList."""
