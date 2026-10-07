"""
Pydantic models for Project resource validation.

This module contains Pydantic models that correspond to the Project JSON schema,
providing validation for Project resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import ConfigDict, Field, RootModel, model_validator

from rapyuta_io_sdk_v2.models.utils import (
    SDKModel,
    BaseList,
    BaseMetadata,
    BaseObject,
    Subject,
)


class ProjectMember(SDKModel):
    subject: Subject
    role_names: list[str] | None = Field(default=None, alias="roleNames")
    implicit_role_names: list[str] | None = Field(default=None, alias="implicitRoleNames")


class FeaturesVPN(SDKModel):
    enabled: bool = Field(default=False)
    subnets: list[str] | None = None


class FeaturesTracing(SDKModel):
    enabled: bool = Field(default=False)


class FeaturesDockerCache(SDKModel):
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
        if self and self.enabled:
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
        return self

    @model_validator(mode="after")
    def validate_data_directory(self):
        if self and not self.enabled:
            self.data_directory = None
        return self


class Features(SDKModel):
    vpn: FeaturesVPN = Field(default_factory=FeaturesVPN)
    tracing: FeaturesTracing = Field(default_factory=FeaturesTracing)
    docker_cache: FeaturesDockerCache = Field(
        default_factory=FeaturesDockerCache, alias="dockerCache"
    )


class ProjectSpec(SDKModel):
    members: list[ProjectMember] | None = None
    features: Features = Field(default_factory=Features)


class ProjectStatus(SDKModel):
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


class ProjectOwnership(RootModel[dict[str, Any]]):
    """Project owner endpoint payload, retained without assuming its wire shape."""
