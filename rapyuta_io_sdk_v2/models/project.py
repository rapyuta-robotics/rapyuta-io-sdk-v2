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
# Lifecycle helper imports remain local to keep model modules independent.

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import ConfigDict, Field, model_validator

from rapyuta_io_sdk_v2.models.applier import (
    DependencyReference,
    ResourceCapabilities,
    ResourceContext,
    ResourceOutcome,
    ResourceReference,
    ResourceScope,
)
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.resource import ResourceMethods
from rapyuta_io_sdk_v2.models.utils import BaseList, BaseMetadata, BaseObject, Subject

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client


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
            required_values = (
                ("proxy_device", self.proxy_device),
                ("proxy_interface", self.proxy_interface),
                ("registry_secret", self.registry_secret),
                ("registry_url", self.registry_url),
            )
            missing_fields = [
                field for field, value in required_values if value is None
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


def _member_dependencies(
    members: list[ProjectMember] | None,
) -> tuple[DependencyReference, ...]:
    dependencies: list[DependencyReference] = []
    for member in members or []:
        subject = member.subject
        if subject.kind is not None and (
            subject.name is not None or subject.guid is not None
        ):
            dependencies.append(
                DependencyReference(
                    reference=ResourceReference(
                        kind=subject.kind.lower(),
                        name=subject.name,
                        guid=subject.guid,
                    )
                )
            )
        dependencies.extend(
            DependencyReference(
                reference=ResourceReference(kind="role", name=role_name)
            )
            for role_name in member.role_names or []
        )
    return tuple(dependencies)


def _cache_dependencies(features: Features) -> tuple[DependencyReference, ...]:
    cache = features.docker_cache
    if not cache.enabled:
        return ()
    dependencies: list[DependencyReference] = []
    if cache.registry_secret is not None:
        dependencies.append(
            DependencyReference(
                reference=ResourceReference(
                    kind="secret",
                    name=cache.registry_secret,
                    guid=cache.registry_secret,
                )
            )
        )
    if cache.proxy_device is not None:
        dependencies.append(
            DependencyReference(
                reference=ResourceReference(
                    kind="device",
                    name=cache.proxy_device,
                    guid=cache.proxy_device,
                )
            )
        )
    return tuple(dependencies)


class Project(ResourceMethods, BaseObject):
    """Project model."""

    KIND: ClassVar[str] = "Project"
    CAPABILITIES: ClassVar[ResourceCapabilities] = ResourceCapabilities(
        create=True,
        update=True,
        delete=True,
        apply_policy="create_or_update",
        readiness_kind="project",
    )

    model_config = ConfigDict(extra="forbid")

    kind: Literal["Project"] | None = "Project"
    metadata: BaseMetadata
    spec: ProjectSpec
    status: ProjectStatus | None = None

    def readiness_state(self) -> tuple[str | None, bool, bool]:
        """Return the observed state, readiness, and terminal failure flags."""
        status = self.status.status if self.status is not None else None
        return status, status == "Success", status == "Error"

    def resource_dependencies(
        self, *, scope: ResourceScope | None = None
    ) -> tuple[DependencyReference, ...]:
        """Declare explicit members, roles, cache Secret, and external Device."""
        del scope
        return (
            *_member_dependencies(self.spec.members),
            *_cache_dependencies(self.spec.features),
        )

    def create_object(self, client: Client, *, context: ResourceContext) -> Project:
        """Create a Project with selected organization routing."""
        from rapyuta_io_sdk_v2.apply._resources.project import (  # noqa: PLC0415
            _project_context,
            _project_payload,
        )
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write,
        )

        context = _project_context(self, context)
        payload = _project_payload(self, context)
        return record_write(
            context,
            "created",
            lambda: client.create_project(payload, **organization_options(context)),
        )

    async def create_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> Project:
        """Create a Project through the native asynchronous endpoint."""
        from rapyuta_io_sdk_v2.apply._resources.project import (  # noqa: PLC0415
            _project_context,
            _project_payload,
        )
        from rapyuta_io_sdk_v2.apply._resources.standard import (  # noqa: PLC0415
            organization_options,
            record_write_async,
        )

        context = _project_context(self, context)
        payload = _project_payload(self, context)
        return await record_write_async(
            context,
            "created",
            lambda: client.create_project(payload, **organization_options(context)),
        )

    def update_object(self, client: Client, *, context: ResourceContext) -> Project:
        """Resolve and update the target Project in organization scope."""
        from rapyuta_io_sdk_v2.apply._resources.project import update_project  # noqa: PLC0415

        return update_project(client, self, context=context)

    async def update_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> Project:
        """Resolve and update a Project with native asynchronous reads/writes."""
        from rapyuta_io_sdk_v2.apply._resources.project import update_project_async  # noqa: PLC0415

        return await update_project_async(client, self, context=context)

    def apply(self, client: Client, *, context: ResourceContext) -> ResourceOutcome:
        """Apply Project features, including two-step Docker-cache provisioning."""
        from rapyuta_io_sdk_v2.apply._resources.project import apply_project  # noqa: PLC0415

        return apply_project(self, client, context=context)

    async def apply_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> ResourceOutcome:
        """Apply Project features with native async cache provisioning."""
        from rapyuta_io_sdk_v2.apply._resources.project import apply_project_async  # noqa: PLC0415

        return await apply_project_async(self, client, context=context)

    def _delete_object(self, client: Client, *, context: ResourceContext) -> None:
        """Delete this Project by its resolved GUID."""
        from rapyuta_io_sdk_v2.apply._resources.project import delete_project  # noqa: PLC0415

        delete_project(client, self, context=context)

    async def _delete_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> None:
        """Delete this Project through native async lookup and mutation calls."""
        from rapyuta_io_sdk_v2.apply._resources.project import delete_project_async  # noqa: PLC0415

        await delete_project_async(client, self, context=context)


class ProjectList(BaseList[Project]):
    """List of Project resources."""
