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

"""Pydantic models for Deployment resource validation.

This module contains Pydantic models that correspond to the Deployment JSON schema,
providing validation for Deployment resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, Literal

from pydantic import (
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    Depends,
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

if TYPE_CHECKING:
    from collections.abc import Iterable


class DeploymentMetadata(BaseMetadata):
    """Metadata for Deployment resource."""

    depends: PackageDepends | None = None
    generation: int | None = None


class EnvArgsSpec(SDKModel):
    """Deployment environment variable value or secret reference."""

    name: str
    value: str | None = None
    value_from: ValueFrom | None = Field(
        alias="valueFrom",
        default=None,
        description="Populate the env var's value from a Secret key reference",
    )
    exposed: bool | None = None
    exposed_name: str | None = Field(default=None, alias="exposedName")

    @field_validator("value", mode="before")
    @classmethod
    def coerce_value_to_str(cls, v: object) -> str | None:
        """Convert scalar environment values to strings.

        Args:
            v: Field value supplied to the validator.
        """
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
    def handle_empty_depends(cls, data: object) -> object:
        """Handle empty depends dictionaries by converting them to None.

        Args:
            data: Raw resource data supplied before model validation.
        """
        if isinstance(data, dict) and "depends" in data:
            depends = data["depends"]
            # If depends is an empty dictionary, set it to None
            if isinstance(depends, dict) and not depends:
                data["depends"] = None
        return data

    @field_validator("mount_path", mode="before")
    @classmethod
    def check_absolute_path(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Reject relative mount paths.

        Args:
            v: Field value supplied to the validator.
            info: Field name and previously validated sibling values.
        """
        if v is not None and not pathlib.Path(v).is_absolute():
            message = f"{info.field_name} must be an absolute path."
            raise ValueError(message)
        return v


class DeploymentStaticRoute(SDKModel):
    """Static route configuration matching Go DeploymentStaticRoute struct."""

    name: str | None = None
    url: str | None = None
    depends: StaticRouteDepends

    @model_validator(mode="before")
    @classmethod
    def handle_empty_depends(cls, data: object) -> object:
        """Handle empty depends dictionaries by converting them to None.

        Args:
            data: Raw resource data supplied before model validation.
        """
        if isinstance(data, dict) and "depends" in data:
            depends = data["depends"]
            # If depends is an empty dictionary, set it to None
            if isinstance(depends, dict) and not depends:
                data["depends"] = None
        return data


class DeploymentROSNetwork(SDKModel):
    """ROS Network configuration matching Go DeploymentROSNetwork struct."""

    depends: NetworkDepends
    domain_id: int | None = Field(
        alias="domainID",
        default=None,
        description="ROS Domain ID",
    )
    interface: str | None = Field(default=None, description="Network interface")

    @model_validator(mode="before")
    @classmethod
    def handle_empty_depends(cls, data: object) -> object:
        """Handle empty depends dictionaries by converting them to None.

        Args:
            data: Raw resource data supplied before model validation.
        """
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
    block_until_synced: bool | None = Field(alias="blockUntilSynced", default=False)


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
    def handle_empty_depends(data: object) -> object:
        """Handle empty depends dictionaries by converting them to None.

        Args:
            data: Raw resource data supplied before model validation.
        """
        if isinstance(data, dict) and "depends" in data:
            depends = data["depends"]
            # If depends is an empty dictionary, set it to None
            if isinstance(depends, dict) and not depends:
                data["depends"] = None
        return data


class DeploymentSpec(SDKModel):
    """Deployment runtime, dependencies, volumes, and process overrides."""

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
        alias="networkInterface",
        default=None,
        description=(
            "Network interface to use for ROS networks. "
            "Takes precedence over any interface specified in rosNetworks entries."
        ),
    )

    @model_validator(mode="after")
    def validate_runtime_and_volumes(self) -> DeploymentSpec:
        """Validate each volume against the selected deployment runtime."""
        validator = {
            "device": _validate_device_volume,
            "cloud": _validate_cloud_volume,
        }.get(self.runtime)
        if validator:
            for volume in self.volumes or []:
                validator(volume)
        return self


class ExecutableStatus(SDKModel):
    """Container lifecycle, image, restart history, and exit result."""

    name: str | None = None
    # Container image, including tag, that this executable runs.
    image: str | None = None
    status: ExecutableStatusType | None = None
    error_code: str | None = None
    reason: str | None = None
    restart_count: int | None = None
    exit_code: int | None = None


class DependentDeploymentStatus(SDKModel):
    """Lifecycle and errors for a prerequisite deployment."""

    name: str | None = None
    guid: str | None = None
    status: DeploymentStatusType | None = None
    phase: DeploymentPhase | None = None
    error_codes: list[str] | None = None


class DependentNetworkStatus(SDKModel):
    """Lifecycle and errors for a prerequisite network."""

    name: str | None = None
    guid: str | None = None
    status: DeploymentStatusType | None = None
    phase: DeploymentPhase | None = None
    error_codes: list[str] | None = None


class DependentDiskStatus(SDKModel):
    """Lifecycle and errors for a prerequisite disk."""

    name: str | None = None
    guid: str | None = None
    status: str | None = None
    error_codes: str | None = None


class Dependencies(SDKModel):
    """Observed deployment, network, and disk dependency status."""

    deployments: list[DependentDeploymentStatus] | None = None
    networks: list[DependentNetworkStatus] | None = None
    disks: list[DependentDiskStatus] | None = Field(default=None, alias="disk")


class DeploymentStatus(SDKModel):
    """Deployment lifecycle and executable and dependency status."""

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
        """Return package, runtime, deployment, and network dependencies in order."""
        dependencies = _dependency_names([self.metadata.depends], "package")
        dependencies.extend(self._runtime_dependencies())
        dependencies.extend(_dependency_names(self.spec.depends or [], "deployment"))
        dependencies.extend(
            _dependency_names(
                (network.depends for network in self.spec.ros_networks or []), "network"
            )
        )
        return dependencies

    def _runtime_dependencies(self) -> list[str]:
        if self.spec.runtime == "cloud":
            disks = _dependency_names(
                (volume.depends for volume in self.spec.volumes or []), "disk"
            )
            routes = _dependency_names(
                (route.depends for route in self.spec.static_routes or []),
                "staticroute",
            )
            return disks + routes
        if self.spec.runtime == "device" and self.spec.device:
            return _dependency_names([self.spec.device.depends], "device")
        return []


class DeploymentList(BaseList[Deployment]):
    """List of deployments using BaseList."""


def _dependency_names(
    dependencies: Iterable[Depends | PackageDepends | None], kind: str
) -> list[str]:
    return [
        f"{kind}:{dependency.name_or_guid}"
        for dependency in dependencies
        if dependency is not None
    ]


def _validate_device_volume(volume: DeploymentVolume) -> None:
    if volume.depends and getattr(volume.depends, "kind", None) in (
        "managedService",
        "cloudService",
    ):
        message = (
            f"Device runtime cannot use cloud volume dependency: {volume.depends.kind}"
        )
        raise ValueError(message)


def _validate_cloud_volume(volume: DeploymentVolume) -> None:
    if any(value is not None for value in (volume.uid, volume.gid, volume.perm)):
        message = (
            "Cloud runtime cannot use device-specific volume fields: uid, gid, perm"
        )
        raise ValueError(message)


class DeploymentHistoryMetadata(BaseMetadata):
    """Historical deployment generation and common resource metadata."""

    name: str | None = None
    generation: int | None = None


class DeploymentHistoryStatus(SDKModel):
    """Deployment status recorded for a historical generation."""

    error_codes: list[str] | None = None
    phase: DeploymentPhase | None = None
    status: DeploymentStatusType | None = None


class DeploymentHistory(SDKModel):
    """One deployment history entry."""

    metadata: DeploymentHistoryMetadata
    status: DeploymentHistoryStatus


class DeploymentHistoryList(BaseList[DeploymentHistory]):
    """Historical deployment generations."""


class DeploymentGraphNode(SDKModel):
    """Named resource in a deployment dependency graph."""

    name: str = Field(alias="Name")
    type: Literal["Deployment", "Network", "Disk"] = Field(alias="Type")


class DeploymentGraphEdge(SDKModel):
    """Directed dependency between two graph nodes."""

    from_: DeploymentGraphNode = Field(alias="From")
    to: DeploymentGraphNode = Field(alias="To")
    text: str = Field(alias="Text")
    type: Literal[
        "Deployment", "Network", "Disk", "ROSTopic", "ROSService", "ROSAction"
    ] = Field(alias="Type")


class DeploymentGraph(SDKModel):
    """Dependency graph preserving the server's capitalized JSON keys."""

    nodes: list[DeploymentGraphNode] | None = Field(default=None, alias="Nodes")
    lines: list[DeploymentGraphEdge] | None = Field(default=None, alias="Lines")
