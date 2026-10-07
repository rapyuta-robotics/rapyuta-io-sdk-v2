"""
Pydantic models for Deployment resource validation.

This module contains Pydantic models that correspond to the Deployment JSON schema,
providing validation for Deployment resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

from os import path

from typing import Any, Literal

from pydantic import ConfigDict, Field, RootModel, model_validator, field_validator

from rapyuta_io_sdk_v2.models.utils import (
    SDKModel,
    resource_key,
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
    StaticRouteDepends,
    ValueFrom,
)


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
        if self.runtime == "device" and self.volumes:
            # For device runtime, volumes should not have cloud-specific depends
            for volume in self.volumes:
                if volume.depends and hasattr(volume.depends, "kind"):
                    # Device volumes should depend on disks, not cloud resources
                    if volume.depends.kind in ["managedService", "cloudService"]:
                        raise ValueError(
                            f"Device runtime cannot use cloud volume dependency: {volume.depends.kind}"
                        )
        elif self.runtime == "cloud" and self.volumes:
            # For cloud runtime, volumes should not have device-specific fields
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

    def list_dependencies(self) -> list[str] | None:
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

        return dependencies


class DeploymentList(BaseList[Deployment]):
    """List of deployments using BaseList."""

    pass


class DeploymentHistory(RootModel[dict[str, Any] | list[Any]]):
    """Deployment history response, retaining server-defined event structures."""


class DeploymentGraph(RootModel[dict[str, Any]]):
    """Experimental graph response, preserving its opaque graph schema."""
