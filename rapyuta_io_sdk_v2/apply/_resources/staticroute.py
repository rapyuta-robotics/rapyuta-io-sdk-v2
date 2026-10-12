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

"""StaticRoute logical identity and canonical platform routing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rapyuta_io_sdk_v2.apply._resources.standard import (
    project_options,
    record_write,
    record_write_async,
    scoped_copy,
)
from rapyuta_io_sdk_v2.apply.errors import (
    ApplierValidationError,
    MissingResourceContextError,
)
from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.models.applier import ResourceContext
    from rapyuta_io_sdk_v2.models.staticroute import StaticRoute


@dataclass(frozen=True, slots=True)
class _StaticRouteLookup:
    client: Client | AsyncClient
    resource: StaticRoute
    context: ResourceContext
    logical_name: str
    canonical: str


def _selected_context(
    resource: StaticRoute,
    client: Client | AsyncClient,
    context: ResourceContext,
) -> ResourceContext:
    metadata = scoped_copy(resource, context).metadata
    organization_guid = metadata.organization_guid or client.config.organization_guid
    project_guid = metadata.project_guid or client.config.project_guid
    return context.model_copy(
        update={
            "scope": context.scope.model_copy(
                update={
                    "organization_guid": organization_guid,
                    "project_guid": project_guid,
                }
            )
        }
    )


def _short_guid(client: Client, context: ResourceContext, resource: StaticRoute) -> str:
    if context.scope.organization_short_guid is not None:
        return context.scope.organization_short_guid
    organization_guid = context.scope.organization_guid
    if organization_guid is None:
        msg = "StaticRoute routing requires an organization GUID"
        raise MissingResourceContextError(
            msg,
            resource=resource.resource_identity(scope=context.scope),
            operation="apply",
            required_context=("organization_guid", "organization_short_guid"),
        )
    organization = client.get_organization(organization_guid)
    if organization.metadata.short_guid is None:
        msg = "Organization response did not include its short GUID"
        raise MissingResourceContextError(
            msg,
            resource=resource.resource_identity(scope=context.scope),
            operation="apply",
            required_context=("organization_short_guid",),
        )
    return organization.metadata.short_guid


async def _short_guid_async(
    client: AsyncClient, context: ResourceContext, resource: StaticRoute
) -> str:
    if context.scope.organization_short_guid is not None:
        return context.scope.organization_short_guid
    organization_guid = context.scope.organization_guid
    if organization_guid is None:
        msg = "StaticRoute routing requires an organization GUID"
        raise MissingResourceContextError(
            msg,
            resource=resource.resource_identity(scope=context.scope),
            operation="apply",
            required_context=("organization_guid", "organization_short_guid"),
        )
    organization = await client.get_organization(organization_guid)
    if organization.metadata.short_guid is None:
        msg = "Organization response did not include its short GUID"
        raise MissingResourceContextError(
            msg,
            resource=resource.resource_identity(scope=context.scope),
            operation="apply",
            required_context=("organization_short_guid",),
        )
    return organization.metadata.short_guid


def _canonical_name(logical_name: str, short_guid: str) -> str:
    suffix = f"-{short_guid}"
    return logical_name if logical_name.endswith(suffix) else f"{logical_name}{suffix}"


def _find_staticroute(
    client: Client, name: str, context: ResourceContext
) -> StaticRoute | None:
    try:
        return client.get_staticroute(name, **project_options(context))
    except HttpNotFoundError:
        return None


async def _find_staticroute_async(
    client: AsyncClient, name: str, context: ResourceContext
) -> StaticRoute | None:
    try:
        return await client.get_staticroute(name, **project_options(context))
    except HttpNotFoundError:
        return None


def _list_exact_staticroutes(lookup: _StaticRouteLookup) -> StaticRoute | None:
    matches: list[StaticRoute] = []
    continuation = 0
    seen: set[int] = set()
    while True:
        page = lookup.client.list_staticroutes(
            cont=continuation,
            limit=50,
            names=[lookup.logical_name, lookup.canonical],
            **project_options(lookup.context),
        )
        matches.extend(
            item
            for item in page.items or []
            if item.metadata.name in {lookup.logical_name, lookup.canonical}
        )
        metadata = page.metadata
        token = metadata.continue_ if metadata is not None else None
        if token is None:
            break
        if token in seen:
            msg = "StaticRoute lookup repeated a continuation token"
            raise ApplierValidationError(
                msg,
                category="pagination",
                identities=(
                    lookup.resource.resource_identity(scope=lookup.context.scope),
                ),
            )
        seen.add(token)
        continuation = token
    if len(matches) > 1:
        msg = "StaticRoute lookup returned multiple exact matches"
        raise ApplierValidationError(
            msg,
            category="ambiguous",
            identities=(lookup.resource.resource_identity(scope=lookup.context.scope),),
        )
    return matches[0] if matches else None


async def _list_exact_staticroutes_async(
    lookup: _StaticRouteLookup,
) -> StaticRoute | None:
    matches: list[StaticRoute] = []
    continuation = 0
    seen: set[int] = set()
    while True:
        page = await lookup.client.list_staticroutes(
            cont=continuation,
            limit=50,
            names=[lookup.logical_name, lookup.canonical],
            **project_options(lookup.context),
        )
        matches.extend(
            item
            for item in page.items or []
            if item.metadata.name in {lookup.logical_name, lookup.canonical}
        )
        metadata = page.metadata
        token = metadata.continue_ if metadata is not None else None
        if token is None:
            break
        if token in seen:
            msg = "StaticRoute lookup repeated a continuation token"
            raise ApplierValidationError(
                msg,
                category="pagination",
                identities=(
                    lookup.resource.resource_identity(scope=lookup.context.scope),
                ),
            )
        seen.add(token)
        continuation = token
    if len(matches) > 1:
        msg = "StaticRoute lookup returned multiple exact matches"
        raise ApplierValidationError(
            msg,
            category="ambiguous",
            identities=(lookup.resource.resource_identity(scope=lookup.context.scope),),
        )
    return matches[0] if matches else None


def resolve_staticroute(
    client: Client, resource: StaticRoute, *, context: ResourceContext
) -> StaticRoute | None:
    """Resolve an exact route by logical name or its organization suffix."""
    context = _selected_context(resource, client, context)
    logical_name = resource.metadata.name
    found = _find_staticroute(client, logical_name, context)
    if found is not None and found.metadata.name == logical_name:
        return found
    short_guid = _short_guid(client, context, resource)
    canonical = _canonical_name(logical_name, short_guid)
    if found is not None and found.metadata.name == canonical:
        return found
    if canonical != logical_name:
        found = _find_staticroute(client, canonical, context)
        if found is not None and found.metadata.name == canonical:
            return found
    lookup = _StaticRouteLookup(client, resource, context, logical_name, canonical)
    return _list_exact_staticroutes(lookup)


async def resolve_staticroute_async(
    client: AsyncClient, resource: StaticRoute, *, context: ResourceContext
) -> StaticRoute | None:
    """Resolve a canonical route using native asynchronous lookup calls."""
    context = _selected_context(resource, client, context)
    logical_name = resource.metadata.name
    found = await _find_staticroute_async(client, logical_name, context)
    if found is not None and found.metadata.name == logical_name:
        return found
    short_guid = await _short_guid_async(client, context, resource)
    canonical = _canonical_name(logical_name, short_guid)
    if found is not None and found.metadata.name == canonical:
        return found
    if canonical != logical_name:
        found = await _find_staticroute_async(client, canonical, context)
        if found is not None and found.metadata.name == canonical:
            return found
    lookup = _StaticRouteLookup(client, resource, context, logical_name, canonical)
    return await _list_exact_staticroutes_async(lookup)


def update_staticroute(
    client: Client, resource: StaticRoute, *, context: ResourceContext
) -> StaticRoute:
    """Update a route by its canonical server-side routing name."""
    context = _selected_context(resource, client, context)
    existing = resolve_staticroute(client, resource, context=context)
    if existing is None:
        msg = "StaticRoute was not found for update"
        raise HttpNotFoundError(msg)
    canonical = existing.metadata.name
    payload = scoped_copy(resource, context)
    metadata = payload.metadata.model_copy(update={"name": canonical})
    payload = payload.model_copy(update={"metadata": metadata})
    return record_write(
        context,
        "updated",
        lambda: client.update_staticroute(
            canonical, payload, **project_options(context)
        ),
    )


async def update_staticroute_async(
    client: AsyncClient, resource: StaticRoute, *, context: ResourceContext
) -> StaticRoute:
    """Update a route by its canonical name with native async calls."""
    context = _selected_context(resource, client, context)
    existing = await resolve_staticroute_async(client, resource, context=context)
    if existing is None:
        msg = "StaticRoute was not found for update"
        raise HttpNotFoundError(msg)
    canonical = existing.metadata.name
    payload = scoped_copy(resource, context)
    metadata = payload.metadata.model_copy(update={"name": canonical})
    payload = payload.model_copy(update={"metadata": metadata})
    return await record_write_async(
        context,
        "updated",
        lambda: client.update_staticroute(
            canonical, payload, **project_options(context)
        ),
    )


def delete_staticroute(
    client: Client, resource: StaticRoute, *, context: ResourceContext
) -> None:
    """Resolve and delete by the canonical platform routing name."""
    context = _selected_context(resource, client, context)
    existing = resolve_staticroute(client, resource, context=context)
    if existing is None:
        msg = "StaticRoute was not found"
        raise HttpNotFoundError(msg)
    record_write(
        context,
        "deleted",
        lambda: client.delete_staticroute(
            existing.metadata.name, **project_options(context)
        ),
    )


async def delete_staticroute_async(
    client: AsyncClient, resource: StaticRoute, *, context: ResourceContext
) -> None:
    """Resolve and delete the canonical route through native async calls."""
    context = _selected_context(resource, client, context)
    existing = await resolve_staticroute_async(client, resource, context=context)
    if existing is None:
        msg = "StaticRoute was not found"
        raise HttpNotFoundError(msg)
    await record_write_async(
        context,
        "deleted",
        lambda: client.delete_staticroute(
            existing.metadata.name, **project_options(context)
        ),
    )


__all__ = [
    "delete_staticroute",
    "delete_staticroute_async",
    "resolve_staticroute",
    "resolve_staticroute_async",
    "update_staticroute",
    "update_staticroute_async",
]
