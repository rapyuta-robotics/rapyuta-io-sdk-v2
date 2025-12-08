"""
Pydantic models for Secret resource validation.

This module contains Pydantic models that correspond to the Secret JSON schema,
providing validation for Secret resources to help users identify missing or
incorrect fields.
"""

from typing import Literal
from typing_extensions import override

from pydantic import BaseModel, Field

from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    DeviceDepends,
    Runtime,
)


class DockerSpec(BaseModel):
    registry: str = Field(
        default="https://index.docker.io/v1/", description="Docker registry URL"
    )
    username: str = Field(description="Username for docker registry authentication")
    email: str = Field(description="Email for docker registry authentication")


class DockerSpecCreate(DockerSpec):
    password: str = Field(description="Password for docker registry authentication")


class SecretSpec(BaseModel):
    """Specification for Secret resource."""

    docker: DockerSpec = Field(
        description="Docker registry configuration when type is Docker"
    )
    runtime: Runtime | None = None
    depends: DeviceDepends | None = None


class SecretSpecCreate(BaseModel):
    docker: DockerSpecCreate
    runtime: Runtime | None = None
    depends: DeviceDepends | None = None


class Secret(BaseObject):
    """Secret model."""

    kind: Literal["Secret"] | None = "Secret"
    metadata: BaseMetadata
    spec: SecretSpec = Field(description="Specification for the Secret resource")


class SecretCreate(Secret):
    spec: SecretSpecCreate

    @override
    def list_dependencies(self) -> list[str] | None:
        runtime = self.spec.runtime

        if not runtime or runtime == "cloud":
            return None

        if self.spec.depends is not None:
            device_name = self.spec.depends.name_or_guid
            return [f"device:{device_name}"]

        return None


class SecretList(BaseList[Secret]):
    """List of secrets using BaseList."""

    pass
