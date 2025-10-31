"""
Pydantic models for Deployment resource validation.

This module contains Pydantic models that correspond to the Deployment JSON schema,
providing validation for Deployment resources to help users identify missing or
incorrect fields.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

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
    StaticRouteDepends,
)


class DeploymentMetadata(BaseMetadata):
    """Metadata for Deployment resource."""

    depends: PackageDepends | None = None
    generation: int | None = None


class EnvArgsSpec(BaseModel):
    name: str
    value: str | None = None


class DeploymentVolume(BaseModel):
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


class DeploymentStaticRoute(BaseModel):
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


class DeploymentROSNetwork(BaseModel):
    """ROS Network configuration matching Go DeploymentROSNetwork struct."""

    depends: NetworkDepends
    domainID: int | None | None = Field(default=None, default=None, description="ROS Domain ID")
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


class DeploymentParamConfig(BaseModel):
    """Param configuration matching Go DeploymentParamConfig struct."""

    enabled: bool | None = None
    trees: list[str] | None = None
    blockUntilSynced: bool | None = Field(default=False)


class DeploymentVPNConfig(BaseModel):
    """VPN configuration matching Go DeploymentVPNConfig struct."""

    enabled: bool | None = Field(default=False)


class DeploymentFeatures(BaseModel):
    """Features configuration matching Go DeploymentFeatures struct."""

    params: DeploymentParamConfig | None = None
    vpn: DeploymentVPNConfig | None = None


class DeploymentDevice(BaseModel):
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


class DeploymentSpec(BaseModel):
    runtime: Runtime
    depends: list[DeploymentDepends] | None = None
    device: DeploymentDevice | None = None
    restart: RestartPolicy = Field(default="always")
    envArgs: list[EnvArgsSpec] | None = None
    volumes: list[DeploymentVolume] | None = None
    rosNetworks: list[DeploymentROSNetwork] | None = None
    features: DeploymentFeatures | None = None
    staticRoutes: list[DeploymentStaticRoute] | None = None

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


class ExecutableStatus(BaseModel):
    name: str
    status: ExecutableStatusType | None = None
    error_code: str | None = None
    reason: str | None = None
    restart_count: int | None = None
    exit_code: int | None = None


class DependentDeploymentStatus(BaseModel):
    name: str | None = None
    guid: str | None = None
    status: DeploymentStatusType | None = None
    phase: DeploymentPhase | None = None
    errorCodes: list[str] | None = None


class DependentNetworkStatus(BaseModel):
    name: str | None = None
    guid: str | None = None
    status: DeploymentStatusType | None = None
    phase: DeploymentPhase | None = None
    errorCodes: list[str] | None = Field(default=None, alias="error_codes")


class DependentDiskStatus(BaseModel):
    name: str | None = None
    guid: str | None = None
    status: str | None = None
    errorCode: str | None = Field(default=None, alias="error_codes")


class Dependencies(BaseModel):
    deployments: list[DependentDeploymentStatus] | None = None
    networks: list[DependentNetworkStatus] | None = None
    disks: list[DependentDiskStatus] | None = Field(default=None, alias="disk")


class DeploymentStatus(BaseModel):
    phase: DeploymentPhase | None = None
    status: DeploymentStatusType | None = None
    error_codes: list[str] | None = Field(default=None, alias="errorCodes")
    executables_status: dict[str, ExecutableStatus] | None = Field(
        default=None, alias="executablesStatus"
    )
    dependencies: Dependencies | None = None


class Deployment(BaseObject):
    """Deployment model."""

    kind: Literal["Deployment"] | None = "Deployment"
    metadata: DeploymentMetadata
    spec: DeploymentSpec
    status: DeploymentStatus | None = None


class DeploymentList(BaseList[Deployment]):
    """List of deployments using BaseList."""

    pass
