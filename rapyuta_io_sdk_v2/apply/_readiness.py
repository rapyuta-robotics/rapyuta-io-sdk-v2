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

"""Finite, explicit readiness polling for resources that expose provisioning."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Protocol, cast

from rapyuta_io_sdk_v2.apply._resources.standard import project_options
from rapyuta_io_sdk_v2.apply.errors import ReadinessError
from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError
from rapyuta_io_sdk_v2.models.applier import (
    ResourceContext,
    ResourceIdentity,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.models.applier import ResourceScope
    from rapyuta_io_sdk_v2.models.deployment import Deployment
    from rapyuta_io_sdk_v2.models.disk import Disk
    from rapyuta_io_sdk_v2.models.network import Network
    from rapyuta_io_sdk_v2.models.project import Project
    from rapyuta_io_sdk_v2.models.utils import BaseMetadata, ListMeta

_PAGE_LIMIT = 50


class _ReadinessResource(Protocol):
    def readiness_state(self) -> tuple[str | None, bool, bool]:
        """Return the state, readiness, and terminal failure flags."""
        ...


class _NamedResource(_ReadinessResource, Protocol):
    @property
    def metadata(self) -> BaseMetadata | None: ...

    def resource_identity(
        self, *, scope: ResourceScope | None = None
    ) -> ResourceIdentity: ...


class _ResourcePage[T](Protocol):
    @property
    def items(self) -> Sequence[T] | None: ...

    @property
    def metadata(self) -> ListMeta | None: ...


def _observed_state(item: _ReadinessResource | None) -> tuple[str | None, bool, bool]:
    return item.readiness_state() if item is not None else (None, False, False)


def _identity(
    kind: str, name_or_guid: str, context: ResourceContext
) -> ResourceIdentity:
    return ResourceIdentity(
        kind=kind,
        scope=context.scope,
        name=name_or_guid,
    )


def _failure(
    identity: ResourceIdentity,
    *,
    category: str,
    last_state: str | None,
) -> ReadinessError:
    if category == "terminal":
        message = f"{identity.kind} entered terminal readiness state {last_state}"
    elif category == "pagination":
        message = f"{identity.kind} readiness lookup repeated a continuation token"
    elif category == "ambiguous":
        message = f"{identity.kind} readiness lookup returned multiple exact matches"
    else:
        message = f"{identity.kind} readiness checks exhausted"
    return ReadinessError(
        message,
        identity=identity,
        category=category,
        last_state=last_state,
    )


def _one_match[T](matches: list[T], identity: ResourceIdentity) -> T | None:
    if len(matches) > 1:
        raise _failure(identity, category="ambiguous", last_state=None)
    return matches[0] if matches else None


def _exact_deployment(
    items: list[Deployment],
    name_or_guid: str,
    identity: ResourceIdentity,
    *,
    by_guid: bool = False,
) -> Deployment | None:
    matches = [
        item
        for item in items
        if (item.metadata.guid if by_guid else item.metadata.name) == name_or_guid
    ]
    return _one_match(matches, identity)


def _pages_sync[T](
    list_page: Callable[..., _ResourcePage[T]],
    *,
    identity: ResourceIdentity,
    context: ResourceContext,
    filters: dict[str, object],
) -> list[T]:
    matches: list[T] = []
    continuation = 0
    seen: set[int] = set()
    while True:
        page = list_page(
            cont=continuation,
            limit=_PAGE_LIMIT,
            **filters,
            **project_options(context),
        )
        items = page.items or []
        matches.extend(items)
        metadata = page.metadata
        next_token = metadata.continue_ if metadata is not None else None
        if next_token is None:
            return matches
        if next_token in seen:
            raise _failure(identity, category="pagination", last_state=str(next_token))
        seen.add(next_token)
        continuation = next_token


async def _pages_async[T](
    list_page: Callable[..., Awaitable[_ResourcePage[T]]],
    *,
    identity: ResourceIdentity,
    context: ResourceContext,
    filters: dict[str, object],
) -> list[T]:
    matches: list[T] = []
    continuation = 0
    seen: set[int] = set()
    while True:
        page = await list_page(
            cont=continuation,
            limit=_PAGE_LIMIT,
            **filters,
            **project_options(context),
        )
        items = page.items or []
        matches.extend(items)
        metadata = page.metadata
        next_token = metadata.continue_ if metadata is not None else None
        if next_token is None:
            return matches
        if next_token in seen:
            raise _failure(identity, category="pagination", last_state=str(next_token))
        seen.add(next_token)
        continuation = next_token


def _exact_named[T: _NamedResource](
    list_page: Callable[..., _ResourcePage[T]], resource: T, context: ResourceContext
) -> T | None:
    identity = resource.resource_identity(scope=context.scope)
    name = cast("BaseMetadata", resource.metadata).name
    try:
        items = _pages_sync(
            list_page, identity=identity, context=context, filters={"names": [name]}
        )
    except HttpNotFoundError:
        return None
    return _matching_name(items, name, identity)


async def _exact_named_async[T: _NamedResource](
    list_page: Callable[..., Awaitable[_ResourcePage[T]]],
    resource: T,
    context: ResourceContext,
) -> T | None:
    identity = resource.resource_identity(scope=context.scope)
    name = cast("BaseMetadata", resource.metadata).name
    try:
        items = await _pages_async(
            list_page, identity=identity, context=context, filters={"names": [name]}
        )
    except HttpNotFoundError:
        return None
    return _matching_name(items, name, identity)


def _matching_name[T: _NamedResource](
    items: list[T], name: str, identity: ResourceIdentity
) -> T | None:
    return _one_match(
        [
            item
            for item in items
            if item.metadata is not None and item.metadata.name == name
        ],
        identity,
    )


def _project_observation(
    client: Client, resource: Project, context: ResourceContext
) -> Project | None:
    identity = resource.resource_identity(scope=context.scope)
    if resource.metadata.guid is not None:
        try:
            return client.get_project(
                resource.metadata.guid,
                organization_guid=context.scope.organization_guid,
            )
        except HttpNotFoundError:
            return None
    items = _pages_sync(
        client.list_projects,
        identity=identity,
        context=context,
        filters={
            "name": resource.metadata.name,
            "organizations": [
                resource.metadata.organization_guid or context.scope.organization_guid
            ],
        },
    )
    matches = [
        item
        for item in items
        if item.metadata.name == resource.metadata.name
        and item.metadata.organization_guid
        == (resource.metadata.organization_guid or context.scope.organization_guid)
    ]
    return _one_match(matches, identity)


async def _project_observation_async(
    client: AsyncClient, resource: Project, context: ResourceContext
) -> Project | None:
    identity = resource.resource_identity(scope=context.scope)
    if resource.metadata.guid is not None:
        try:
            return await client.get_project(
                resource.metadata.guid,
                organization_guid=context.scope.organization_guid,
            )
        except HttpNotFoundError:
            return None
    items = await _pages_async(
        client.list_projects,
        identity=identity,
        context=context,
        filters={
            "name": resource.metadata.name,
            "organizations": [
                resource.metadata.organization_guid or context.scope.organization_guid
            ],
        },
    )
    matches = [
        item
        for item in items
        if item.metadata.name == resource.metadata.name
        and item.metadata.organization_guid
        == (resource.metadata.organization_guid or context.scope.organization_guid)
    ]
    return _one_match(matches, identity)


def _poll(
    identity: ResourceIdentity,
    context: ResourceContext,
    observe: Callable[[], _ReadinessResource | None],
) -> None:
    options = context.readiness
    last_state: str | None = None
    for round_index in range(options.checks):
        last_state, ready, terminal = _observed_state(observe())
        if ready:
            return
        if terminal:
            raise _failure(identity, category="terminal", last_state=last_state)
        if round_index + 1 < options.checks and options.interval > 0:
            time.sleep(options.interval)
    raise _failure(identity, category="exhausted", last_state=last_state)


async def _poll_async(
    identity: ResourceIdentity,
    context: ResourceContext,
    observe: Callable[[], Awaitable[_ReadinessResource | None]],
) -> None:
    options = context.readiness
    last_state: str | None = None
    for round_index in range(options.checks):
        last_state, ready, terminal = _observed_state(await observe())
        if ready:
            return
        if terminal:
            raise _failure(identity, category="terminal", last_state=last_state)
        if round_index + 1 < options.checks and options.interval > 0:
            await asyncio.sleep(options.interval)
    raise _failure(identity, category="exhausted", last_state=last_state)


def wait_for_resource(
    resource: object,
    client: Client,
    *,
    context: ResourceContext,
    kind: str,
) -> None:
    """Wait synchronously for Disk, Network, or Project provisioning."""
    if kind == "disk":
        disk = cast("Disk", resource)
        _poll(
            disk.resource_identity(scope=context.scope),
            context,
            lambda: _exact_named(client.list_disks, disk, context),
        )
    elif kind == "network":
        network = cast("Network", resource)
        _poll(
            network.resource_identity(scope=context.scope),
            context,
            lambda: _exact_named(client.list_networks, network, context),
        )
    elif kind == "project":
        project = cast("Project", resource)
        _poll(
            project.resource_identity(scope=context.scope),
            context,
            lambda: _project_observation(client, project, context),
        )
    else:
        msg = f"unknown readiness kind: {kind}"
        raise ValueError(msg)


async def wait_for_resource_async(
    resource: object,
    client: AsyncClient,
    *,
    context: ResourceContext,
    kind: str,
) -> None:
    """Wait asynchronously for Disk, Network, or Project provisioning."""
    if kind == "disk":
        disk = cast("Disk", resource)
        await _poll_async(
            disk.resource_identity(scope=context.scope),
            context,
            lambda: _exact_named_async(client.list_disks, disk, context),
        )
    elif kind == "network":
        network = cast("Network", resource)
        await _poll_async(
            network.resource_identity(scope=context.scope),
            context,
            lambda: _exact_named_async(client.list_networks, network, context),
        )
    elif kind == "project":
        project = cast("Project", resource)
        await _poll_async(
            project.resource_identity(scope=context.scope),
            context,
            lambda: _project_observation_async(client, project, context),
        )
    else:
        msg = f"unknown readiness kind: {kind}"
        raise ValueError(msg)


def wait_for_deployment_dependencies(
    resource: Deployment, client: Client, *, context: ResourceContext
) -> None:
    """Wait independently for each explicitly flagged Deployment prerequisite."""
    for dependency in resource.spec.depends or []:
        if not dependency.wait:
            continue
        identity = _identity("deployment", dependency.name_or_guid, context)

        def observe(
            dependency_name: str = dependency.name_or_guid,
            dependency_identity: ResourceIdentity = identity,
        ) -> Deployment | None:
            items = _pages_sync(
                client.list_deployments,
                identity=dependency_identity,
                context=context,
                filters={"names": [dependency_name]},
            )
            match = _exact_deployment(items, dependency_name, dependency_identity)
            if match is None:
                items = _pages_sync(
                    client.list_deployments,
                    identity=dependency_identity,
                    context=context,
                    filters={"guids": [dependency_name]},
                )
                match = _exact_deployment(
                    items, dependency_name, dependency_identity, by_guid=True
                )
            return match

        _poll(identity, context, observe)


async def wait_for_deployment_dependencies_async(
    resource: Deployment, client: AsyncClient, *, context: ResourceContext
) -> None:
    """Wait natively for each explicitly flagged Deployment prerequisite."""
    for dependency in resource.spec.depends or []:
        if not dependency.wait:
            continue
        identity = _identity("deployment", dependency.name_or_guid, context)

        async def observe(
            dependency_name: str = dependency.name_or_guid,
            dependency_identity: ResourceIdentity = identity,
        ) -> Deployment | None:
            items = await _pages_async(
                client.list_deployments,
                identity=dependency_identity,
                context=context,
                filters={"names": [dependency_name]},
            )
            match = _exact_deployment(items, dependency_name, dependency_identity)
            if match is None:
                items = await _pages_async(
                    client.list_deployments,
                    identity=dependency_identity,
                    context=context,
                    filters={"guids": [dependency_name]},
                )
                match = _exact_deployment(
                    items, dependency_name, dependency_identity, by_guid=True
                )
            return match

        await _poll_async(identity, context, observe)


__all__ = [
    "wait_for_deployment_dependencies",
    "wait_for_deployment_dependencies_async",
    "wait_for_resource",
    "wait_for_resource_async",
]
