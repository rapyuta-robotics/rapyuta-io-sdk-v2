"""
Pydantic models for Package resource validation.

This module contains Pydantic models that correspond to the Package JSON schema,
providing validation for Package resources to help users identify missing or
incorrect fields.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from rapyuta_io_sdk_v2.models.utils import (
    Architecture,
    BaseList,
    BaseMetadata,
    RestartPolicy,
    Runtime,
)

# --- Helper Models ---

EndpointProto = Literal[
    "external-http",
    "external-https",
    "external-tls-tcp",
    "internal-tcp",
    "internal-tcp-range",
    "internal-udp",
    "internal-udp-range",
]


class StringMap(dict[str, str]):
    pass


class LivenessProbe(BaseModel):
    httpGet: dict | None = None
    exec: dict | None = None
    tcpSocket: dict | None = None
    initialDelaySeconds: int | None = Field(default=None, ge=1)
    timeoutSeconds: int | None = Field(default=None, ge=10)
    periodSeconds: int | None = Field(default=None, ge=1)
    successThreshold: int | None = Field(default=None, ge=1)
    failureThreshold: int | None = Field(default=None, ge=1)


class EnvironmentSpec(BaseModel):
    name: str
    description: str | None = None
    default: str | None = None
    exposed: bool | None = Field(default=None)
    exposedName: str | None = None

    @field_validator("exposedName")
    @classmethod
    def validate_exposed_name(cls, v, info):
        if info.data.get("exposed") and not v:
            raise ValueError("exposedName is required when exposed is True")
        return v


class Limits(BaseModel):
    cpu: float | None = Field(default=None, ge=0, le=256)
    memory: float | int | None = Field(default=None, ge=0)


class DeviceDockerSpec(BaseModel):
    image: str
    imagePullPolicy: str | None = Field(default="IfNotPresent")
    pullSecret: dict | None = None


class CloudDockerSpec(BaseModel):
    image: str
    pullSecret: dict | None = None


class Executable(BaseModel):
    name: str | None = None
    type: Literal["docker", "preInstalled"] = Field(default="docker")
    docker: DeviceDockerSpec | None = None
    command: str | list[str] | None = None
    args: list[str] | None = None
    limits: Limits | None = None
    livenessProbe: LivenessProbe | None = None
    uid: int | None = None
    gid: int | None = None


class EndpointSpec(BaseModel):
    name: str
    type: EndpointProto | None = None
    port: int | None = None
    targetPort: int | None = None
    portRange: str | None = None


class DeviceComponentInfoSpec(BaseModel):
    arch: Architecture | None = Field(default="amd64")
    restart: RestartPolicy | None = Field(default="always")


class CloudComponentInfoSpec(BaseModel):
    replicas: int | None = Field(default=1)


class RosEndpointSpec(BaseModel):
    type: str
    name: str
    compression: bool | None = Field(default=None)
    scoped: bool | None = Field(default=None)
    targeted: bool | None = Field(default=None)
    qos: str | None = None
    timeout: int | float | None = None


class RosComponentSpec(BaseModel):
    enabled: bool | None = Field(default=False)
    version: Literal["kinetic", "melodic", "noetic", "foxy"] | None = None
    rosEndpoints: list[RosEndpointSpec] | None = None


class PackageSpec(BaseModel):
    runtime: Runtime | None = None
    executables: list[Executable] | None = None
    environmentVars: list[EnvironmentSpec] | None = None
    ros: RosComponentSpec | None = None
    endpoints: list[EndpointSpec] | None = None
    device: DeviceComponentInfoSpec | None = None
    cloud: CloudComponentInfoSpec | None = None
    hostPID: bool | None = None

    @model_validator(mode="after")
    @staticmethod
    def check_spec_device_or_cloud(obj):
        if obj.runtime == "device" and obj.cloud is not None:
            raise ValueError("'cloud' section must not be set when runtime is 'device'.")
        if obj.runtime == "cloud" and obj.device is not None:
            raise ValueError("'device' section must not be set when runtime is 'cloud'.")
        return obj


class PackageMetadata(BaseMetadata):
    version: str | None
    description: str | None = Field(default=None)


class Package(BaseModel):
    """Package model."""

    apiVersion: str | None = Field(default="api.rapyuta.io/v2")
    kind: Literal["Package"] = Field(default="Package")
    metadata: PackageMetadata
    spec: PackageSpec

    def list_dependencies(self) -> list[str] | None:
        dependencies: list[str] = []

        if self.spec.executables:
            for exec in self.spec.executables:
                if exec.docker and exec.docker.pullSecret:
                    secret = exec.docker.pullSecret.depends.nameOrGUID
                    if secret is not None:
                        dependencies.append(f"secret:{secret}")

        if dependencies == []:
            return None

        return dependencies


class PackageList(BaseList[Package]):
    """List of packages using BaseList."""

    pass
