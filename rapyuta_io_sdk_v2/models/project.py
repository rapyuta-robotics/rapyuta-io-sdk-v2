"""
Pydantic models for Project resource validation.

This module contains Pydantic models that correspond to the Project JSON schema,
providing validation for Project resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import ConfigDict, Field, RootModel, model_validator

from rapyuta_io_sdk_v2.exceptions import HttpAlreadyExistsError, HttpNotFoundError
from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    SDKModel,
    Subject,
)
from rapyuta_io_sdk_v2.resource_operations import (
    ApplyError,
    Pause,
    ReadinessError,
    Request,
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

    resource_kind: ClassVar[str] = "Project"

    endpoint: ClassVar[str] = "project"

    mutable: ClassVar[bool] = True

    def dependencies(self) -> list[str]:
        cache = self.spec.features.docker_cache
        return (
            [f"secret:{cache.registry_secret}"]
            if cache.enabled and cache.registry_secret
            else []
        )

    def _lookup(self):
        if self.metadata.guid:
            return self.metadata.guid
        matches = yield from self._named_resources("list_projects")
        if not matches or not matches[0].metadata.guid:
            raise HttpNotFoundError(f"Project {self.metadata.name} not found")
        if len(matches) != 1:
            raise ApplyError(f"Ambiguous project name {self.metadata.name}")
        return matches[0].metadata.guid

    def _update(self):
        guid = yield from self._lookup()
        return (yield Request("update_project", (self,), {"project_guid": guid}))

    def _delete(self):
        guid = yield from self._lookup()
        yield Request("delete_project", (guid,))

    def _create(self):
        if not self.spec.features.docker_cache.enabled:
            return (yield Request("create_project", (self,)))
        # DockerCache is supported only by the update endpoint.
        try:
            yield from self._lookup()
        except HttpNotFoundError:
            initial = self.model_copy(deep=True)
            initial.spec.features.docker_cache.enabled = False
            for name in type(initial.spec.features.docker_cache).model_fields:
                if name != "enabled":
                    setattr(initial.spec.features.docker_cache, name, None)
            created = yield Request("create_project", (initial,))
            self.metadata.guid = created.metadata.guid
        # Report UPDATED, even when an initial shell project was necessary.
        raise HttpAlreadyExistsError("Project requires update for DockerCache")

    def _wait(self, attempts: int, interval: float):
        for attempt in range(attempts):
            page = yield Request("list_projects", kwargs={"name": self.metadata.name})
            matches = [r for r in page.items if r.metadata.name == self.metadata.name]
            status = getattr(matches[0], "status", None) if matches else None
            state = getattr(status, "status", None)
            if state == "Success":
                return
            if state in ("Error", "Deleting"):
                raise ReadinessError(f"{self.identity} entered {state}")
            if attempt + 1 < attempts:
                yield Pause(interval)
        raise ReadinessError(f"{self.identity} readiness timed out")


class ProjectList(BaseList[Project]):
    """List of Project resources."""

    pass


class ProjectOwnership(RootModel[dict[str, Any]]):
    """Project owner endpoint payload, retained without assuming its wire shape."""
