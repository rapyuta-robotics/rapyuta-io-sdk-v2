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

"""Pydantic models for Package resource validation.

This module contains Pydantic models that correspond to the Package JSON schema,
providing validation for Package resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, ValidationInfo, field_validator, model_validator

from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.utils import (
    Architecture,
    BaseList,
    BaseMetadata,
    RestartPolicy,
    Runtime,
    SecretDepends,
    ValueFrom,
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
    """Dictionary of string keys and string values."""


class PullSecret(SDKModel):
    """Reference to credentials used to pull a container image."""

    depends: SecretDepends | None = None

    @field_validator("depends", mode="before")
    @classmethod
    def empty_dict_to_none(cls, value: dict) -> dict | None:
        """Normalize empty configuration dictionaries to absent values.

        Args:
            value: Field value supplied to the validator.
        """
        if value == {}:
            return None
        return value


class HttpHeader(SDKModel):
    """HTTP header sent by a container health probe."""

    name: str
    value: str


class HttpGet(SDKModel):
    """HTTP endpoint and headers used by a health probe."""

    path: str
    port: int
    host: str | None = Field(default=None)
    scheme: str | None = Field(default="HTTP")
    http_headers: list[HttpHeader] | None = Field(alias="httpHeaders", default=None)


class LivenessProbe(SDKModel):
    """Container health checks and their timing and failure thresholds."""

    http_get: HttpGet | None = Field(default=None, alias="httpGet")
    exec: dict | None = None
    tcp_socket: dict | None = Field(default=None, alias="tcpSocket")
    initial_delay_seconds: int | None = Field(
        alias="initialDelaySeconds", default=None, ge=1
    )
    timeout_seconds: int | None = Field(alias="timeoutSeconds", default=None, ge=10)
    period_seconds: int | None = Field(alias="periodSeconds", default=None, ge=1)
    success_threshold: int | None = Field(alias="successThreshold", default=None, ge=1)
    failure_threshold: int | None = Field(alias="failureThreshold", default=None, ge=1)


class EnvironmentSpec(SDKModel):
    """Environment variable defaults, exposure, and secret references."""

    name: str
    description: str | None = None
    default: str | None = None
    value_from: ValueFrom | None = Field(
        alias="valueFrom",
        default=None,
        description="Populate the env var's value from a Secret key reference",
    )
    exposed: bool | None = Field(default=None)
    exposed_name: str | None = Field(default=None, alias="exposedName")

    @field_validator("exposed_name")
    @classmethod
    def validate_exposed_name(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Require an exposed name for exposed environment variables.

        Args:
            v: Field value supplied to the validator.
            info: Field name and previously validated sibling values.
        """
        if info.data.get("exposed") and not v:
            message = "exposedName is required when exposed is True"
            raise ValueError(message)
        return v


class Limits(SDKModel):
    """CPU and memory limits for a container executable."""

    cpu: float | None = Field(default=None, ge=0, le=256)
    memory: float | int | None = Field(default=None, ge=0)


class DockerSpec(SDKModel):
    """Container image, image pull policy, and registry credentials."""

    image: str
    image_pull_policy: str | None = Field(
        alias="imagePullPolicy", default="IfNotPresent"
    )
    pull_secret: PullSecret | None = Field(default=None, alias="pullSecret")


class Executable(SDKModel):
    """Container image, launch command, health probe, and process settings."""

    name: str | None = None
    type: Literal["docker", "preInstalled"] = Field(default="docker")
    docker: DockerSpec | None = None
    command: str | list[str] | None = None
    run_as_bash: bool = Field(default=False, alias="runAsBash")
    args: list[str] | None = None
    limits: Limits | None = None
    liveness_probe: LivenessProbe | None = Field(default=None, alias="livenessProbe")
    uid: int | None = None
    gid: int | None = None

    @model_validator(mode="after")
    def prepend_bash_to_command(self) -> Executable:
        """Build the executable command with an optional Bash wrapper."""
        if self.command is None:
            return self

        command: list[str] = []

        if self.run_as_bash:
            command = ["/bin/bash", "-c"]

        if isinstance(self.command, str):
            command.append(self.command)
        elif isinstance(self.command, list):
            command.extend(self.command)

        self.command = command

        return self


class EndpointSpec(SDKModel):
    """Network endpoint ports and transport exposed by a package."""

    name: str
    type: EndpointProto | None = None
    port: int | None = None
    target_port: int | None = Field(default=None, alias="targetPort")
    port_range: str | None = Field(default=None, alias="portRange")


class DeviceComponentInfoSpec(SDKModel):
    """Architecture and restart policy for a device package."""

    arch: Architecture | None = Field(default="amd64")
    restart: RestartPolicy | None = Field(default="always")


class CloudComponentInfoSpec(SDKModel):
    """Replica count for a cloud package."""

    replicas: int | None = Field(default=1)


class RosEndpointSpec(SDKModel):
    """ROS communication endpoint and delivery settings."""

    type: str
    name: str
    compression: bool | None = Field(default=None)
    scoped: bool | None = Field(default=None)
    targeted: bool | None = Field(default=None)
    qos: str | None = None
    timeout: int | float | None = None


class RosComponentSpec(SDKModel):
    """ROS version and endpoints enabled by a package."""

    enabled: bool | None = Field(default=False)
    version: Literal["kinetic", "melodic", "noetic", "foxy"] | None = None
    ros_endpoints: list[RosEndpointSpec] | None = Field(
        default=None, alias="rosEndpoints"
    )


class PackageSpec(SDKModel):
    """Runtime, executables, and exposed interfaces for a package."""

    runtime: Runtime | None = None
    executables: list[Executable] | None = None
    environment_vars: list[EnvironmentSpec] | None = Field(
        default=None, alias="environmentVars"
    )
    ros: RosComponentSpec | None = None
    endpoints: list[EndpointSpec] | None = None
    device: DeviceComponentInfoSpec | None = None
    cloud: CloudComponentInfoSpec | None = None
    host_pid: bool | None = Field(default=None, alias="hostPID")

    @model_validator(mode="after")
    @staticmethod
    def check_spec_device_or_cloud(obj: PackageSpec) -> PackageSpec:
        """Reject configuration for a runtime other than the selected runtime.

        Args:
            obj: Validated package specification.
        """
        if obj.runtime == "device" and obj.cloud is not None:
            message = "'cloud' section must not be set when runtime is 'device'."
            raise ValueError(message)
        if obj.runtime == "cloud" and obj.device is not None:
            message = "'device' section must not be set when runtime is 'cloud'."
            raise ValueError(message)
        return obj

    @model_validator(mode="before")
    @classmethod
    def empty_dicts_to_none(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Normalize empty configuration sections to absent values.

        Args:
            values: Raw package specification fields.
        """
        for key, value in values.items():
            if isinstance(value, dict) and not value:
                values[key] = None
        return values


class PackageMetadata(BaseMetadata):
    # A Package is identified by its name and version together, so the version
    # is part of its identity rather than optional detail. Allowing it to be
    # null or empty lets two distinct versions of a Package become
    # indistinguishable to any consumer that keys on (name, version).
    """Package identity, including its required version."""

    version: str = Field(min_length=1, description="Version of the package")
    description: str | None = Field(default=None)


class Package(SDKModel):
    """Package model."""

    api_version: str | None = Field(alias="apiVersion", default="api.rapyuta.io/v2")
    kind: Literal["Package"] = Field(default="Package")
    metadata: PackageMetadata
    spec: PackageSpec

    def list_dependencies(self) -> list[str] | None:
        """Return image pull secrets required by the package executables."""
        dependencies = []
        for executable in self.spec.executables or []:
            secret = _pull_secret_name(executable)
            if secret is not None:
                dependencies.append(f"secret:{secret}")
        return dependencies or None


class PackageList(BaseList[Package]):
    """List of packages using BaseList."""


def _pull_secret_name(executable: Executable) -> str | None:
    if executable.docker and executable.docker.pull_secret:
        return getattr(executable.docker.pull_secret.depends, "name_or_guid", None)
    return None
