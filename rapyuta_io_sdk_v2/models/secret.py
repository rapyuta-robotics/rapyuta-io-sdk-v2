"""
Pydantic models for Secret resource validation.

This module contains Pydantic models that correspond to the Secret JSON schema,
providing validation for Secret resources to help users identify missing or
incorrect fields.
"""

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
    registry: str = Field(
        default="https://index.docker.io/v1/", description="Docker registry URL"
    )
    username: str = Field(description="Username for docker registry authentication")
    email: str = Field(description="Email for docker registry authentication")


class DockerSpecCreate(DockerSpec):
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
        description="List of keys present in the secret (read-only, returned by server)",
    )
    runtime: Runtime | None = None
    depends: DeviceDepends | None = None


class SecretSpecCreate(BaseModel):
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
    spec: SecretSpecCreate

    @model_validator(mode="after")
    def validate_create_fields(self):
        spec = self.spec
        if spec.type == "Docker":
            if spec.docker is None or not spec.docker.password:
                raise ValueError(
                    "'spec.docker.password' is required when creating a Docker secret"
                )
        elif spec.type == "Opaque":
            if not spec.data:
                raise ValueError(
                    "'spec.data' is required when creating an Opaque secret"
                )
        return self

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
