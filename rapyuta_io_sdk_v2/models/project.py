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

"""Pydantic models for Project resource validation.

This module contains Pydantic models that correspond to the Project JSON schema,
providing validation for Project resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject, Subject


class ProjectMember(SDKModel):
    """Project subject with assigned and inherited roles."""

    subject: Subject
    role_names: list[str] | None = Field(default=None, alias="roleNames")
    implicit_role_names: list[str] | None = Field(
        default=None, alias="implicitRoleNames"
    )


class FeaturesVPN(SDKModel):
    """Project VPN enablement and allowed subnets."""

    enabled: bool = Field(default=False)
    subnets: list[str] | None = None


class FeaturesTracing(SDKModel):
    """Project tracing enablement."""

    enabled: bool = Field(default=False)


class FeaturesDockerCache(SDKModel):
    """Docker cache proxy, registry credentials, and storage settings."""

    enabled: bool = Field(default=False)
    proxy_device: str | None = Field(default=None, alias="proxyDevice")
    proxy_interface: str | None = Field(default=None, alias="proxyInterface")
    registry_secret: str | None = Field(default=None, alias="registrySecret")
    registry_url: str | None = Field(default=None, alias="registryURL")
    data_directory: str | None = Field(
        default="/opt/rapyuta/volumes/docker-cache/", alias="dataDirectory"
    )

    @model_validator(mode="after")
    def validate_enabled_requires_all_fields(self) -> FeaturesDockerCache:
        """Require Docker cache connection settings when the cache is enabled."""
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
                message = (
                    "Following fields should be present if docker_cache is enabled: "
                    f"{', '.join(missing_fields)}"
                )
                raise ValueError(message)
        return self

    @model_validator(mode="after")
    def validate_data_directory(self) -> FeaturesDockerCache:
        """Clear the cache data directory when Docker caching is disabled."""
        if self and not self.enabled:
            self.data_directory = None
        return self


class Features(SDKModel):
    """Optional networking, tracing, and image cache features for a project."""

    vpn: FeaturesVPN = Field(default_factory=FeaturesVPN)
    tracing: FeaturesTracing = Field(default_factory=FeaturesTracing)
    docker_cache: FeaturesDockerCache = Field(
        default_factory=FeaturesDockerCache, alias="dockerCache"
    )


class ProjectSpec(SDKModel):
    """Project memberships and feature configuration."""

    members: list[ProjectMember] | None = None
    features: Features = Field(default_factory=Features)


class ProjectStatus(SDKModel):
    """Project lifecycle and feature provisioning results."""

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
