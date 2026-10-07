"""
Pydantic models for Deployment resource validation.

This module contains Pydantic models that correspond to the Deployment JSON schema,
providing validation for Deployment resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

import asyncio
import time

from os import path
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import ConfigDict, Field, RootModel, field_validator, model_validator

from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError
from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    DeploymentDepends,
    DeploymentPhase,
    DeploymentStatusType,
    DeviceDepends,
    DiskDepends,
    ExecutableStatusType,
    NetworkDepends,
    PackageDepends,
    RestartPolicy,
    Runtime,
    SDKModel,
    StaticRouteDepends,
    ValueFrom,
    resource_key,
)
from rapyuta_io_sdk_v2.resource_operations import ReadinessError


if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.context import RequestContext


class DeploymentMetadata(BaseMetadata):
    """Metadata for Deployment resource."""

    depends: PackageDepends | None = None
    generation: int | None = None


class EnvArgsSpec(SDKModel):
    name: str
    value: str | None = None
    value_from: ValueFrom | None = Field(
        default=None,
        description="Populate the env var's value from a Secret key reference",
        alias="valueFrom",
    )
    exposed: bool | None = None
    exposed_name: str | None = Field(default=None, alias="exposedName")

    @field_validator("value", mode="before")
    @classmethod
    def coerce_value_to_str(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            return str(v).lower() if isinstance(v, bool) else str(v)
        return v


class DeploymentVolume(SDKModel):
    """Unified volume spec matching Go DeploymentVolume struct."""

    exec_name: str | None = Field(default=None, alias="execName")
    mount_path: str | None = Field(default=None, alias="mountPath")
    sub_path: str | None = Field(default=None, alias="subPath")
    uid: int | None = None
    gid: int | None = None
    perm: int | None = None
    depends: DiskDepends | None = None

    @model_validator(mode="before")
    @classmethod
    def handle_empty_depends(cls, data):
        """Handle empty depends dictionaries by converting them to None."""
        if isinstance(data, dict) and "depends" in data:
            depends = data["depends"]
            # If depends is an empty dictionary, set it to None
            if isinstance(depends, dict) and not depends:
                data["depends"] = None
        return data

    @field_validator("mount_path", mode="before")
    @classmethod
    def check_absolute_path(cls, v, info):
        if v is not None and not path.isabs(v):
            raise ValueError(f"{info.field_name} must be an absolute path.")
        return v


class DeploymentStaticRoute(SDKModel):
    """Static route configuration matching Go DeploymentStaticRoute struct."""

    name: str | None = None
    url: str | None = None
    depends: StaticRouteDepends

    @model_validator(mode="before")
    @classmethod
    def handle_empty_depends(cls, data):
        """Handle empty depends dictionaries by converting them to None."""
        if isinstance(data, dict) and "depends" in data:
            depends = data["depends"]
            # If depends is an empty dictionary, set it to None
            if isinstance(depends, dict) and not depends:
                data["depends"] = None
        return data


class DeploymentROSNetwork(SDKModel):
    """ROS Network configuration matching Go DeploymentROSNetwork struct."""

    depends: NetworkDepends
    domain_id: int | None | None = Field(
        default=None, description="ROS Domain ID", alias="domainID"
    )
    interface: str | None = Field(default=None, description="Network interface")

    @model_validator(mode="before")
    @classmethod
    def handle_empty_depends(cls, data):
        """Handle empty depends dictionaries by converting them to None."""
        if isinstance(data, dict) and "depends" in data:
            depends = data["depends"]
            # If depends is an empty dictionary, set it to None
            if isinstance(depends, dict) and not depends:
                data["depends"] = None
        return data


class DeploymentParamConfig(SDKModel):
    """Param configuration matching Go DeploymentParamConfig struct."""

    enabled: bool | None = None
    trees: list[str] | None = None
    block_until_synced: bool | None = Field(default=False, alias="blockUntilSynced")


class DeploymentVPNConfig(SDKModel):
    """VPN configuration matching Go DeploymentVPNConfig struct."""

    enabled: bool | None = Field(default=False)


class DeploymentFeatures(SDKModel):
    """Features configuration matching Go DeploymentFeatures struct."""

    params: DeploymentParamConfig | None = None
    vpn: DeploymentVPNConfig | None = None


class DeploymentDevice(SDKModel):
    """Device configuration matching Go DeploymentDevice struct."""

    depends: DeviceDepends

    @model_validator(mode="before")
    @staticmethod
    def handle_empty_depends(data):
        """Handle empty depends dictionaries by converting them to None."""
        if isinstance(data, dict) and "depends" in data:
            depends = data["depends"]
            # If depends is an empty dictionary, set it to None
            if isinstance(depends, dict) and not depends:
                data["depends"] = None
        return data


class DeploymentSpec(SDKModel):
    runtime: Runtime
    depends: list[DeploymentDepends] | None = None
    device: DeploymentDevice | None = None
    restart: RestartPolicy | None = None
    env_args: list[EnvArgsSpec] | None = Field(default=None, alias="envArgs")
    volumes: list[DeploymentVolume] | None = None
    ros_networks: list[DeploymentROSNetwork] | None = Field(
        default=None, alias="rosNetworks"
    )
    features: DeploymentFeatures | None = None
    static_routes: list[DeploymentStaticRoute] | None = Field(
        default=None, alias="staticRoutes"
    )
    service_account: str | None = Field(default=None, alias="serviceAccount")
    network_interface: str | None = Field(
        default=None,
        description=(
            "Network interface to use for ROS networks. "
            "Takes precedence over any interface specified in rosNetworks entries."
        ),
        alias="networkInterface",
    )

    @model_validator(mode="after")
    def validate_runtime_and_volumes(self):
        """Validate that runtime and volume configurations are compatible."""
        if self.runtime == "cloud" and self.volumes:
            for volume in self.volumes:
                if any(
                    [
                        volume.uid is not None,
                        volume.gid is not None,
                        volume.perm is not None,
                    ]
                ):
                    raise ValueError(
                        "Cloud runtime cannot use device-specific volume fields: uid, gid, perm"
                    )
        return self


class ExecutableStatus(SDKModel):
    name: str | None = None
    # Container image, including tag, that this executable runs.
    image: str | None = None
    status: ExecutableStatusType | None = None
    error_code: str | None = None
    reason: str | None = None
    restart_count: int | None = None
    exit_code: int | None = None


class DependentDeploymentStatus(SDKModel):
    name: str | None = None
    guid: str | None = None
    status: DeploymentStatusType | None = None
    phase: DeploymentPhase | None = None
    error_codes: list[str] | None = None


class DependentNetworkStatus(SDKModel):
    name: str | None = None
    guid: str | None = None
    status: DeploymentStatusType | None = None
    phase: DeploymentPhase | None = None
    error_codes: list[str] | None = None


class DependentDiskStatus(SDKModel):
    name: str | None = None
    guid: str | None = None
    status: str | None = None
    error_codes: str | None = None


class Dependencies(SDKModel):
    deployments: list[DependentDeploymentStatus] | None = None
    networks: list[DependentNetworkStatus] | None = None
    disks: list[DependentDiskStatus] | None = Field(default=None, alias="disk")


class DeploymentStatus(SDKModel):
    phase: DeploymentPhase | None = None
    status: DeploymentStatusType | None = None
    error_codes: list[str] | None = None
    executables_status: dict[str, ExecutableStatus] | None = None
    dependencies: Dependencies | None = None


class Deployment(BaseObject):
    """Deployment model."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["Deployment"] | None = "Deployment"
    metadata: DeploymentMetadata
    spec: DeploymentSpec
    status: DeploymentStatus | None = None

    def dependencies(self) -> list[str]:
        dependencies: list[str] = []

        # Package Dependency
        if self.metadata.depends is not None:
            key = resource_key(
                "Package",
                self.metadata.depends.name_or_guid,
                self.metadata.depends.version,
            )
            dependencies.append(key)

        if self.spec.runtime == "cloud":
            # Disk Dependency
            if self.spec.volumes:
                for volume in self.spec.volumes:
                    if volume.depends is not None:
                        key = resource_key("disk", volume.depends.name_or_guid)
                        dependencies.append(key)

            # Static Route Dependency
            if self.spec.static_routes:
                for route in self.spec.static_routes:
                    if route.depends is not None:
                        key = resource_key("staticroute", route.depends.name_or_guid)
                        dependencies.append(key)

        # Device Dependency
        if self.spec.runtime == "device" and self.spec.device is not None:
            if self.spec.device.depends:
                key = resource_key("device", self.spec.device.depends.name_or_guid)
                dependencies.append(key)

        # Deployment Dependency
        if self.spec.depends:
            for dep in self.spec.depends:
                key = resource_key("deployment", dep.name_or_guid)
                dependencies.append(key)

        # Network Dependency
        if self.spec.ros_networks:
            for network in self.spec.ros_networks:
                if network.depends is not None:
                    key = resource_key("network", network.depends.name_or_guid)
                    dependencies.append(key)

        for variable in self.spec.env_args or []:
            if variable.value_from is not None:
                reference = variable.value_from.secret_key_ref
                if reference is not None and reference.name:
                    dependencies.append(resource_key("Secret", reference.name))
        if self.spec.service_account:
            dependencies.append(resource_key("ServiceAccount", self.spec.service_account))
        return list(dict.fromkeys(dependencies))

    resource_kind: ClassVar[str] = "Deployment"

    def create(self, client: Client, *, context: RequestContext | None = None):
        return client.create_deployment(self, context=context)

    async def create_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.create_deployment(self, context=context)

    def _delete(self, client: Client, *, context: RequestContext | None = None) -> None:
        client.delete_deployment(self.metadata.name, context=context)

    async def _delete_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> None:
        await client.delete_deployment(self.metadata.name, context=context)

    def prerequisites(
        self,
        client: Client,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None = None,
    ) -> None:
        required = {
            dependency.name_or_guid
            for dependency in (self.spec.depends or [])
            if dependency.wait
        }
        if not required:
            return
        for attempt in range(attempts):
            ready = True
            for name in sorted(required):
                try:
                    deployment = client.get_deployment(name, context=context)
                except HttpNotFoundError:
                    ready = False
                    continue
                state = (
                    deployment.status.status if deployment.status is not None else None
                )
                phase = deployment.status.phase if deployment.status is not None else None
                if state in ("Error", "Stopped") or phase in ("FailedToStart", "Stopped"):
                    raise ReadinessError(f"Dependency deployment:{name} failed")
                ready &= state == "Running"
            if ready:
                return
            if attempt + 1 < attempts:
                time.sleep(interval)
        raise ReadinessError(f"Dependencies did not become ready: {sorted(required)}")

    async def prerequisites_async(
        self,
        client: AsyncClient,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None = None,
    ) -> None:
        required = {
            dependency.name_or_guid
            for dependency in (self.spec.depends or [])
            if dependency.wait
        }
        if not required:
            return
        for attempt in range(attempts):
            ready = True
            for name in sorted(required):
                try:
                    deployment = await client.get_deployment(name, context=context)
                except HttpNotFoundError:
                    ready = False
                    continue
                state = (
                    deployment.status.status if deployment.status is not None else None
                )
                phase = deployment.status.phase if deployment.status is not None else None
                if state in ("Error", "Stopped") or phase in ("FailedToStart", "Stopped"):
                    raise ReadinessError(f"Dependency deployment:{name} failed")
                ready &= state == "Running"
            if ready:
                return
            if attempt + 1 < attempts:
                await asyncio.sleep(interval)
        raise ReadinessError(f"Dependencies did not become ready: {sorted(required)}")


class DeploymentList(BaseList[Deployment]):
    """List of deployments using BaseList."""

    pass


class DeploymentHistory(RootModel[dict[str, Any] | list[Any]]):
    """Deployment history response, retaining server-defined event structures."""


class DeploymentGraph(RootModel[dict[str, Any]]):
    """Experimental graph response, preserving its opaque graph schema."""
