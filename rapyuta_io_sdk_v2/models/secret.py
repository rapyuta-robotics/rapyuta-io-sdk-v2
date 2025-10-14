"""
Pydantic models for Secret resource validation.

This module contains Pydantic models that correspond to the Secret JSON schema,
providing validation for Secret resources to help users identify missing or
incorrect fields.
"""

from pydantic import BaseModel, Field, field_validator

from rapyuta_io_sdk_v2.models.utils import BaseMetadata, BaseList


class DockerSpec(BaseModel):
    """Docker registry configuration for secrets."""

    registry: str = Field(
        default="https://index.docker.io/v1/", description="Docker registry URL"
    )
    username: str = Field(description="Username for docker registry authentication")
    password: str | None = Field(
        default=None, description="Password for docker registry authentication"
    )
    email: str = Field(description="Email for docker registry authentication")

    @field_validator("registry", "username", "password", "email", mode="after")
    @classmethod
    def not_empty(cls, v, info):
        # Only require password if it's not None
        if info.field_name == "password" and v is None:
            return v
        if not v or (isinstance(v, str) and v.strip() == ""):
            raise ValueError(f"{info.field_name} is required and cannot be empty")
        return v


class SecretSpec(BaseModel):
    """Specification for Secret resource."""

    docker: DockerSpec | None = Field(
        default=None, description="Docker registry configuration when type is Docker"
    )


class Secret(BaseModel):
    """Secret model."""

    apiVersion: str | None = None
    kind: str | None = None
    metadata: BaseMetadata | None = None
    spec: SecretSpec = Field(description="Specification for the Secret resource")


class SecretList(BaseList[Secret]):
    """List of secrets using BaseList."""

    pass
