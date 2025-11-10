"""
Pydantic models for Project resource validation.

This module contains Pydantic models that correspond to the Project JSON schema,
providing validation for Project resources to help users identify missing or
incorrect fields.
"""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject, Subject


class ProjectMember(BaseModel):
    subject: Subject
    role_names: list[str] = Field(alias="roleNames")


class FeaturesVPN(BaseModel):
    enabled: bool | None = None
    subnets: list[str] | None = None
    enabled: bool = Field(default=False)


class FeaturesTracing(BaseModel):
    enabled: bool = Field(default=False)


class FeaturesDockerCache(BaseModel):
    enabled: bool = Field(default=False)
    proxy_device: str | None = Field(default=None, alias="proxyDevice")
    proxy_interface: str | None = Field(default=None, alias="proxyInterface")
    registry_secret: str | None = Field(default=None, alias="registrySecret")
    registry_url: str | None = Field(default=None, alias="registryURL")
    data_directory: str | None = Field(
        default="/opt/rapyuta/volumes/docker-cache/", alias="dataDirectory"
    )

    @model_validator(mode="after")
    def validate_enabled_requires_all_fields(self):
        if self.enabled:
            required_fields = [
                "proxy_device",
                "proxy_interface",
                "registry_secret",
                "registry_url",
            ]
            missing_fields = [
                field for field in required_fields if getattr(self, field) is None
            ]

            if missing_fields:
                raise ValueError(
                    f"Following fields should be present if docker_cache is enabled: {', '.join(missing_fields)}"
                )

    @model_validator(mode="after")
    def validate_data_directory(self):
        if not self.enabled:
            self.dataDirectory = None
        return self


class Features(BaseModel):
    vpn: FeaturesVPN | None = None
    tracing : FeaturesTracing | None = None
    docker_cache: FeaturesDockerCache | None = Field(default=None, alias="dockerCache")


class ProjectSpec(BaseModel):
    members: list[ProjectMember] | None = None
    features: Features | None = None


class ProjectStatus(BaseModel):
    status: Literal["Pending", "Error", "Success", "Deleting", "Unknown"]
    error: str | None = None
    vpn: Literal["Success", "Error", "Disabled", "Pending"] | None = None
    tracing: Literal["Success", "Error", "Disabled", "Pending"] | None = None


class Project(BaseObject):
    """Project model."""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["Project"] | None = "Project"
    metadata: BaseMetadata
    spec: ProjectSpec
    status: ProjectStatus | None = None


class ProjectList(BaseList[Project]):
    """List of Project resources."""

    pass
