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

"""Pydantic models for Secret resource validation.

This module contains Pydantic models that correspond to the Secret JSON schema,
providing validation for Secret resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    DeviceDepends,
    Runtime,
)


class DockerSpec(BaseModel):
    """Registry login details stored in a Docker secret."""

    registry: str = Field(
        default="https://index.docker.io/v1/", description="Docker registry URL"
    )
    username: str = Field(description="Username for docker registry authentication")
    email: str = Field(description="Email for docker registry authentication")


class DockerSpecCreate(DockerSpec):
    """Registry credentials supplied when creating a Docker secret."""

    password: str = Field(description="Password for docker registry authentication")


SecretType = Literal["Docker", "Opaque"]


class SecretSpec(BaseModel):
    """Specification for Secret resource."""

    type: SecretType = Field(
        description="Type of the secret: Docker or Opaque",
    )
    docker: DockerSpec | None = Field(
        default=None,
        description="Docker registry configuration when type is Docker",
    )
    data: dict[str, str] | None = Field(
        default=None,
        description="Arbitrary key-value data for Opaque secrets",
    )
    secret_keys: list[str] | None = Field(
        default=None,
        alias="secretKeys",
        description=(
            "List of keys present in the secret (read-only, returned by server)"
        ),
    )
    runtime: Runtime | None = None
    depends: DeviceDepends | None = None


class SecretSpecCreate(BaseModel):
    """Credential payload and dependency settings for a new secret."""

    type: SecretType = Field(
        description="Type of the secret: Docker or Opaque",
    )
    docker: DockerSpecCreate | None = None
    data: dict[str, str] | None = Field(
        default=None,
        description="Arbitrary key-value data for Opaque secrets",
    )
    runtime: Runtime | None = None
    depends: DeviceDepends | None = None


class Secret(BaseObject):
    """Secret model."""

    kind: Literal["Secret"] | None = "Secret"
    metadata: BaseMetadata
    spec: SecretSpec = Field(description="Specification for the Secret resource")


class SecretCreate(Secret):
    """Secret creation manifest with the required credential payload."""

    spec: SecretSpecCreate

    @model_validator(mode="after")
    def validate_create_fields(self) -> SecretCreate:
        """Require credential fields for the selected secret type."""
        spec = self.spec
        if spec.type == "Docker":
            if spec.docker is None:
                message = "'spec.docker' is required when creating a Docker secret"
                raise ValueError(message)
        elif spec.type == "Opaque" and not spec.data:
            message = "'spec.data' is required when creating an Opaque secret"
            raise ValueError(message)
        return self

    def list_dependencies(self) -> list[str] | None:
        """Return resource dependencies in manifest order."""
        runtime = self.spec.runtime

        if not runtime or runtime == "cloud":
            return None

        if self.spec.depends is not None:
            device_name = self.spec.depends.name_or_guid
            return [f"device:{device_name}"]

        return None


class SecretList(BaseList[Secret]):
    """List of secrets using BaseList."""
