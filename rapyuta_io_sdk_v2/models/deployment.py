"""
Pydantic models for Deployment resource validation.

This module contains Pydantic models that correspond to the Deployment JSON schema,
providing validation for Deployment resources to help users identify missing or
incorrect fields.
"""

from typing import Literal
from pydantic import BaseModel, Field, model_validator

from rapyuta_io_sdk_v2.models.utils import (
    BaseMetadata,
    BaseList,
    Depends,
    DeploymentPhase,
    DeploymentStatusType,
    ExecutableStatusType,
    RestartPolicy,
    Runtime,
)


class StringMap(dict[str, str]):
    pass


# --- Depends Models ---
class PackageDepends(Depends):
    kind: Literal["package"] = Field(default="package")


class DeploymentMetadata(BaseMetadata):
    """Metadata for Deployment resource."""

    depends: PackageDepends | None = None
    generation: int | None = None


class EnvArgsSpec(BaseModel):
    name: str
    value: str | None = None
    exposed: bool | None = None
    exposed_name: str | None = Field(default=None, alias="exposedName")


class DeploymentVolume(BaseModel):
    """Unified volume spec matching Go DeploymentVolume struct."""

    execName: str | None = None
    mountPath: str | None = None
    subPath: str | None = None
    uid: int | None = None
    gid: int | None = None
    perm: int | None = None
    depends: Depends | None = None

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
    depends: Depends | None = None

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


class ManagedServiceSpec(BaseModel):
    depends: dict[str, str] | None = None

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

    domainID: int | None = Field(default=None, description="ROS Domain ID")
    depends: Depends | None = None
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

    depends: Depends | None = None

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


class DeploymentSpec(BaseModel):
    runtime: Runtime
    depends: list[Depends] | None = None
    device: DeploymentDevice | None = None
    restart: RestartPolicy | None = None
    envArgs: list[EnvArgsSpec] | None = None
    volumes: list[DeploymentVolume] | None = None
    rosNetworks: list[DeploymentROSNetwork] | None = None
    features: DeploymentFeatures | None = None
    staticRoutes: list[DeploymentStaticRoute] | None = None
    managedServices: list[ManagedServiceSpec] | None = None

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
    name: str | None = None
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
    error_codes: list[str] | None = None


class DependentNetworkStatus(BaseModel):
    name: str | None = None
    guid: str | None = None
    status: DeploymentStatusType | None = None
    phase: DeploymentPhase | None = None
    error_codes: list[str] | None = None


class DependentDiskStatus(BaseModel):
    name: str | None = None
    guid: str | None = None
    status: str | None = None
    error_codes: str | None = None


class Dependencies(BaseModel):
    deployments: list[DependentDeploymentStatus] | None = None
    networks: list[DependentNetworkStatus] | None = None
    disks: list[DependentDiskStatus] | None = Field(default=None, alias="disk")


class DeploymentStatus(BaseModel):
    phase: DeploymentPhase | None = None
    status: DeploymentStatusType | None = None
    error_codes: list[str] | None = None
    executables_status: dict[str, ExecutableStatus] | None = None
    dependencies: Dependencies | None = None


class Deployment(BaseModel):
    """Deployment model."""

    apiVersion: str | None = None
    kind: str | None = None
    metadata: DeploymentMetadata
    spec: DeploymentSpec
    status: DeploymentStatus | None = None


class DeploymentList(BaseList[Deployment]):
    """List of deployments using BaseList."""

    pass
