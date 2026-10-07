"""
Pydantic models for Project resource validation.

This module contains Pydantic models that correspond to the Project JSON schema,
providing validation for Project resources to help users identify missing or
incorrect fields.
"""

from __future__ import annotations

from rapyuta_io_sdk_v2.resource_operations import Outcome

import asyncio
import time

from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import ConfigDict, Field, RootModel, model_validator

from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError
from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    BaseObject,
    SDKModel,
    Subject,
)
from rapyuta_io_sdk_v2.resource_operations import ApplyError, ReadinessError


if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.context import RequestContext
    from rapyuta_io_sdk_v2.config import Configuration


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
            required_fields = {
                "proxy_device": self.proxy_device,
                "proxy_interface": self.proxy_interface,
                "registry_secret": self.registry_secret,
                "registry_url": self.registry_url,
            }
            missing_fields = [
                name for name, value in required_fields.items() if value is None
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

    mutable: ClassVar[bool] = True

    def create(self, client: Client, *, context: RequestContext | None = None):
        return client.create_project(self, context=context)

    async def create_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        return await client.create_project(self, context=context)

    def bind_context(self, config: Configuration, context: RequestContext | None) -> None:
        super().bind_context(config, context)
        if not self.metadata.organization_guid:
            self.metadata.organization_guid = (
                context.organization_guid
                if context and context.organization_guid is not None
                else config.organization_guid
            )

    def dependencies(self) -> list[str]:
        cache = self.spec.features.docker_cache
        return (
            [f"secret:{cache.registry_secret}"]
            if cache.enabled and cache.registry_secret
            else []
        )

    def _cache_shell(self):
        initial = self.model_copy(deep=True)
        initial.spec.features.docker_cache = FeaturesDockerCache(enabled=False)
        return initial

    def _lookup(self, client: Client, *, context: RequestContext | None = None) -> str:
        if self.metadata.guid:
            return self.metadata.guid
        matches = []
        cursor = 0
        seen = set()
        while True:
            page = client.list_projects(
                name=self.metadata.name, cont=cursor, context=context
            )
            matches.extend(
                resource
                for resource in page.items
                if resource.metadata.name == self.metadata.name
            )
            next_cursor = page.metadata.continue_ if page.metadata is not None else None
            if next_cursor is None or not page.items or len(page.items) < 50:
                break
            if next_cursor in seen:
                raise ApplyError(
                    f"Repeated continuation token while resolving {self.identity}"
                )
            seen.add(next_cursor)
            cursor = next_cursor
        if len(matches) > 1:
            raise ApplyError(f"Ambiguous project name {self.metadata.name}")
        if not matches or not matches[0].metadata.guid:
            raise HttpNotFoundError(f"Project {self.metadata.name} not found")
        return matches[0].metadata.guid

    def update(self, client: Client, *, context: RequestContext | None = None):
        guid = self._lookup(client, context=context)
        return client.update_project(self, project_guid=guid, context=context)

    def _delete(self, client: Client, *, context: RequestContext | None = None) -> None:
        guid = self._lookup(client, context=context)
        client.delete_project(guid, context=context)

    def _apply(
        self,
        client: Client,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None,
    ):
        if not self.spec.features.docker_cache.enabled:
            return super()._apply(client, attempts, interval, context=context)
        try:
            self.metadata.guid = self._lookup(client, context=context)
        except HttpNotFoundError:
            created = client.create_project(self._cache_shell(), context=context)
            self.metadata.guid = created.metadata.guid
        response = self.update(client, context=context)
        self.wait(client, attempts, interval, context=context)
        return Outcome.UPDATED, response

    def wait(
        self,
        client: Client,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None = None,
    ) -> None:
        for attempt in range(attempts):
            page = client.list_projects(name=self.metadata.name, context=context)
            matches = [
                resource
                for resource in page.items
                if resource.metadata.name == self.metadata.name
            ]
            status = matches[0].status if matches else None
            state = status.status if status is not None else None
            if state == "Success":
                return
            if state in ("Error", "Deleting"):
                raise ReadinessError(f"{self.identity} entered {state}")
            if attempt + 1 < attempts:
                time.sleep(interval)
        raise ReadinessError(f"{self.identity} readiness timed out")

    async def _lookup_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> str:
        if self.metadata.guid:
            return self.metadata.guid
        matches = []
        cursor = 0
        seen = set()
        while True:
            page = await client.list_projects(
                name=self.metadata.name, cont=cursor, context=context
            )
            matches.extend(
                resource
                for resource in page.items
                if resource.metadata.name == self.metadata.name
            )
            next_cursor = page.metadata.continue_ if page.metadata is not None else None
            if next_cursor is None or not page.items or len(page.items) < 50:
                break
            if next_cursor in seen:
                raise ApplyError(
                    f"Repeated continuation token while resolving {self.identity}"
                )
            seen.add(next_cursor)
            cursor = next_cursor
        if len(matches) > 1:
            raise ApplyError(f"Ambiguous project name {self.metadata.name}")
        if not matches or not matches[0].metadata.guid:
            raise HttpNotFoundError(f"Project {self.metadata.name} not found")
        return matches[0].metadata.guid

    async def update_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ):
        guid = await self._lookup_async(client, context=context)
        return await client.update_project(self, project_guid=guid, context=context)

    async def _delete_async(
        self, client: AsyncClient, *, context: RequestContext | None = None
    ) -> None:
        guid = await self._lookup_async(client, context=context)
        await client.delete_project(guid, context=context)

    async def _apply_async(
        self,
        client: AsyncClient,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None,
    ):
        if not self.spec.features.docker_cache.enabled:
            return await super()._apply_async(client, attempts, interval, context=context)
        try:
            self.metadata.guid = await self._lookup_async(client, context=context)
        except HttpNotFoundError:
            created = await client.create_project(self._cache_shell(), context=context)
            self.metadata.guid = created.metadata.guid
        response = await self.update_async(client, context=context)
        await self.wait_async(client, attempts, interval, context=context)
        return Outcome.UPDATED, response

    async def wait_async(
        self,
        client: AsyncClient,
        attempts: int,
        interval: float,
        *,
        context: RequestContext | None = None,
    ) -> None:
        for attempt in range(attempts):
            page = await client.list_projects(name=self.metadata.name, context=context)
            matches = [
                resource
                for resource in page.items
                if resource.metadata.name == self.metadata.name
            ]
            status = matches[0].status if matches else None
            state = status.status if status is not None else None
            if state == "Success":
                return
            if state in ("Error", "Deleting"):
                raise ReadinessError(f"{self.identity} entered {state}")
            if attempt + 1 < attempts:
                await asyncio.sleep(interval)
        raise ReadinessError(f"{self.identity} readiness timed out")


class ProjectList(BaseList[Project]):
    """List of Project resources."""

    pass


class ProjectOwnership(RootModel[dict[str, Any]]):
    """Project owner endpoint payload, retained without assuming its wire shape."""
