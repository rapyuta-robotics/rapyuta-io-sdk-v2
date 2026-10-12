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

"""Project create, update, and Docker-cache bootstrap workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rapyuta_io_sdk_v2.apply._lifecycle import (
    _apply_outcome,
    _context_with_journal,
    apply_resource,
    apply_resource_async,
)
from rapyuta_io_sdk_v2.apply._readiness import (
    wait_for_resource,
    wait_for_resource_async,
)
from rapyuta_io_sdk_v2.apply._resources.standard import (
    organization_options,
    record_write,
    record_write_async,
    scoped_copy,
)
from rapyuta_io_sdk_v2.apply.errors import (
    ApplierValidationError,
    MissingResourceContextError,
)
from rapyuta_io_sdk_v2.exceptions import (
    HttpAlreadyExistsError,
    HttpNotFoundError,
    UnauthorizedAccessError,
)
from rapyuta_io_sdk_v2.models.project import (
    Features,
    FeaturesDockerCache,
    Project,
)

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.models.applier import (
        ResourceContext,
        ResourceIdentity,
        ResourceOutcome,
    )


def _project_context(resource: Project, context: ResourceContext) -> ResourceContext:
    metadata_organization = resource.metadata.organization_guid
    selected_organization = context.scope.organization_guid
    if (
        metadata_organization is not None
        and selected_organization is not None
        and metadata_organization != selected_organization
    ):
        msg = "Project organization conflicts with the selected scope"
        raise ApplierValidationError(
            msg,
            category="scope_conflict",
            identities=(resource.resource_identity(scope=context.scope),),
        )
    organization_guid = selected_organization or metadata_organization
    if organization_guid is None:
        msg = "Project operations require an organization GUID"
        raise MissingResourceContextError(
            msg,
            resource=resource.resource_identity(scope=context.scope),
            operation="apply",
            required_context=("organization_guid",),
        )
    return context.model_copy(
        update={
            "scope": context.scope.model_copy(
                update={"organization_guid": organization_guid}
            )
        }
    )


def _project_payload(
    resource: Project,
    context: ResourceContext,
    *,
    project_guid: str | None = None,
) -> Project:
    payload = scoped_copy(resource, context, include_project=False)
    metadata_updates: dict[str, object] = {
        "organization_guid": context.scope.organization_guid
    }
    if project_guid is not None:
        metadata_updates["guid"] = project_guid
    metadata = payload.metadata.model_copy(deep=True, update=metadata_updates)
    return payload.model_copy(update={"metadata": metadata})


def _exact_project_matches(
    items: list[Project], resource: Project, organization_guid: str
) -> list[Project]:
    return [
        item
        for item in items
        if item.metadata.name == resource.metadata.name
        and item.metadata.organization_guid == organization_guid
    ]


def _one_project(matches: list[Project], identity: ResourceIdentity) -> Project | None:
    if len(matches) > 1:
        msg = "Project lookup returned multiple exact matches"
        raise ApplierValidationError(
            msg,
            category="ambiguous",
            identities=(identity,),
        )
    return matches[0] if matches else None


def _find_project(
    client: Client, resource: Project, context: ResourceContext
) -> Project | None:
    identity = resource.resource_identity(scope=context.scope)
    organization_guid = context.scope.organization_guid
    if organization_guid is None:
        msg = "Project lookup requires an organization GUID"
        raise MissingResourceContextError(
            msg,
            resource=identity,
            operation="apply",
            required_context=("organization_guid",),
        )
    matches: list[Project] = []
    continuation = 0
    seen: set[int] = set()
    while True:
        page = client.list_projects(
            cont=continuation,
            limit=50,
            name=resource.metadata.name,
            organizations=[organization_guid],
            **organization_options(context),
        )
        matches.extend(
            _exact_project_matches(page.items or [], resource, organization_guid)
        )
        metadata = page.metadata
        token = metadata.continue_ if metadata is not None else None
        if token is None:
            break
        if token in seen:
            msg = "Project lookup repeated a continuation token"
            raise ApplierValidationError(
                msg,
                category="pagination",
                identities=(identity,),
            )
        seen.add(token)
        continuation = token
    return _one_project(matches, identity)


async def _find_project_async(
    client: AsyncClient, resource: Project, context: ResourceContext
) -> Project | None:
    identity = resource.resource_identity(scope=context.scope)
    organization_guid = context.scope.organization_guid
    if organization_guid is None:
        msg = "Project lookup requires an organization GUID"
        raise MissingResourceContextError(
            msg,
            resource=identity,
            operation="apply",
            required_context=("organization_guid",),
        )
    matches: list[Project] = []
    continuation = 0
    seen: set[int] = set()
    while True:
        page = await client.list_projects(
            cont=continuation,
            limit=50,
            name=resource.metadata.name,
            organizations=[organization_guid],
            **organization_options(context),
        )
        matches.extend(
            _exact_project_matches(page.items or [], resource, organization_guid)
        )
        metadata = page.metadata
        token = metadata.continue_ if metadata is not None else None
        if token is None:
            break
        if token in seen:
            msg = "Project lookup repeated a continuation token"
            raise ApplierValidationError(
                msg,
                category="pagination",
                identities=(identity,),
            )
        seen.add(token)
        continuation = token
    return _one_project(matches, identity)


def update_project(
    client: Client, resource: Project, *, context: ResourceContext
) -> Project:
    """Resolve the exact project GUID and send a private update payload."""
    context = _project_context(resource, context)
    existing = _find_project(client, resource, context)
    project_guid = resource.metadata.guid or (
        existing.metadata.guid if existing is not None else None
    )
    if project_guid is None:
        msg = "Project update requires a resolved project GUID"
        raise MissingResourceContextError(
            msg,
            resource=resource.resource_identity(scope=context.scope),
            operation="update",
            required_context=("project_guid",),
        )
    payload = _project_payload(resource, context, project_guid=project_guid)
    return record_write(
        context,
        "updated",
        lambda: client.update_project(
            payload, project_guid, **organization_options(context)
        ),
    )


async def update_project_async(
    client: AsyncClient, resource: Project, *, context: ResourceContext
) -> Project:
    """Resolve and update a Project with native async SDK calls."""
    context = _project_context(resource, context)
    existing = await _find_project_async(client, resource, context)
    project_guid = resource.metadata.guid or (
        existing.metadata.guid if existing is not None else None
    )
    if project_guid is None:
        msg = "Project update requires a resolved project GUID"
        raise MissingResourceContextError(
            msg,
            resource=resource.resource_identity(scope=context.scope),
            operation="update",
            required_context=("project_guid",),
        )
    payload = _project_payload(resource, context, project_guid=project_guid)
    return await record_write_async(
        context,
        "updated",
        lambda: client.update_project(
            payload, project_guid, **organization_options(context)
        ),
    )


def _cache_base(resource: Project, context: ResourceContext) -> Project:
    requested_features = resource.spec.features or Features()
    features = requested_features.model_copy(
        deep=True,
        update={"docker_cache": FeaturesDockerCache(enabled=False)},
    )
    spec = resource.spec.model_copy(deep=True, update={"features": features})
    source = resource.model_copy(deep=True, update={"spec": spec})
    return _project_payload(source, context)


def _resolve_cache_project(
    resource: Project, client: Client, context: ResourceContext
) -> tuple[str | None, bool]:
    existing = _find_project(client, resource, context)
    if existing is not None:
        return existing.metadata.guid, False
    try:
        created = record_write(
            context,
            "created",
            lambda: client.create_project(
                _cache_base(resource, context), **organization_options(context)
            ),
        )
    except (HttpAlreadyExistsError, UnauthorizedAccessError):
        existing = _find_project(client, resource, context)
        if existing is None:
            raise
        return existing.metadata.guid, False
    project_guid = created.metadata.guid
    if project_guid is None:
        msg = "Project creation response did not include a GUID"
        raise MissingResourceContextError(
            msg,
            resource=resource.resource_identity(scope=context.scope),
            operation="apply",
            required_context=("project_guid",),
        )
    return project_guid, True


async def _resolve_cache_project_async(
    resource: Project, client: AsyncClient, context: ResourceContext
) -> tuple[str | None, bool]:
    existing = await _find_project_async(client, resource, context)
    if existing is not None:
        return existing.metadata.guid, False
    try:
        created = await record_write_async(
            context,
            "created",
            lambda: client.create_project(
                _cache_base(resource, context), **organization_options(context)
            ),
        )
    except (HttpAlreadyExistsError, UnauthorizedAccessError):
        existing = await _find_project_async(client, resource, context)
        if existing is None:
            raise
        return existing.metadata.guid, False
    project_guid = created.metadata.guid
    if project_guid is None:
        msg = "Project creation response did not include a GUID"
        raise MissingResourceContextError(
            msg,
            resource=resource.resource_identity(scope=context.scope),
            operation="apply",
            required_context=("project_guid",),
        )
    return project_guid, True


def _update_cache_project(
    resource: Project,
    client: Client,
    *,
    context: ResourceContext,
    project_guid: str | None,
    created: bool,
) -> ResourceOutcome:
    if project_guid is None:
        msg = "Project update requires a resolved project GUID"
        raise MissingResourceContextError(
            msg,
            resource=resource.resource_identity(scope=context.scope),
            operation="apply",
            required_context=("project_guid",),
        )
    payload = _project_payload(resource, context, project_guid=project_guid)
    record_write(
        context,
        "updated",
        lambda: client.update_project(
            payload, project_guid, **organization_options(context)
        ),
    )
    resolved = resource.model_copy(
        deep=True,
        update={
            "metadata": resource.metadata.model_copy(update={"guid": project_guid})
        },
    )
    wait_for_resource(resolved, client, context=context, kind="project")
    return _apply_outcome(
        resource.resource_identity(scope=context.scope),
        "created" if created else "updated",
        context,
    )


async def _update_cache_project_async(
    resource: Project,
    client: AsyncClient,
    *,
    context: ResourceContext,
    project_guid: str | None,
    created: bool,
) -> ResourceOutcome:
    if project_guid is None:
        msg = "Project update requires a resolved project GUID"
        raise MissingResourceContextError(
            msg,
            resource=resource.resource_identity(scope=context.scope),
            operation="apply",
            required_context=("project_guid",),
        )
    payload = _project_payload(resource, context, project_guid=project_guid)
    await record_write_async(
        context,
        "updated",
        lambda: client.update_project(
            payload, project_guid, **organization_options(context)
        ),
    )
    resolved = resource.model_copy(
        deep=True,
        update={
            "metadata": resource.metadata.model_copy(update={"guid": project_guid})
        },
    )
    await wait_for_resource_async(resolved, client, context=context, kind="project")
    return _apply_outcome(
        resource.resource_identity(scope=context.scope),
        "created" if created else "updated",
        context,
    )


def apply_project(
    resource: Project, client: Client, *, context: ResourceContext
) -> ResourceOutcome:
    """Apply Project membership/features, including the cache bootstrap pair."""
    context = _project_context(resource, context)
    context = _context_with_journal(context)
    cache_enabled = (
        resource.spec.features is not None
        and resource.spec.features.docker_cache.enabled
    )
    if not cache_enabled:
        return apply_resource(resource, client, context=context)

    project_guid, created = _resolve_cache_project(resource, client, context)
    return _update_cache_project(
        resource,
        client,
        context=context,
        project_guid=project_guid,
        created=created,
    )


async def apply_project_async(
    resource: Project, client: AsyncClient, *, context: ResourceContext
) -> ResourceOutcome:
    """Apply Project features with native async cache bootstrap and readiness."""
    context = _project_context(resource, context)
    context = _context_with_journal(context)
    cache_enabled = (
        resource.spec.features is not None
        and resource.spec.features.docker_cache.enabled
    )
    if not cache_enabled:
        return await apply_resource_async(resource, client, context=context)

    project_guid, created = await _resolve_cache_project_async(
        resource, client, context
    )
    return await _update_cache_project_async(
        resource,
        client,
        context=context,
        project_guid=project_guid,
        created=created,
    )


def delete_project(
    client: Client, resource: Project, *, context: ResourceContext
) -> None:
    """Delete the exact Project GUID, resolving by scoped name if needed."""
    context = _project_context(resource, context)
    existing = (
        None
        if resource.metadata.guid is not None
        else _find_project(client, resource, context)
    )
    project_guid = resource.metadata.guid or (
        existing.metadata.guid if existing is not None else None
    )
    if project_guid is None:
        msg = "Project was not found for deletion"
        raise HttpNotFoundError(msg)
    record_write(
        context,
        "deleted",
        lambda: client.delete_project(project_guid, **organization_options(context)),
    )


async def delete_project_async(
    client: AsyncClient, resource: Project, *, context: ResourceContext
) -> None:
    """Delete the exact Project GUID through native async calls."""
    context = _project_context(resource, context)
    existing = (
        None
        if resource.metadata.guid is not None
        else await _find_project_async(client, resource, context)
    )
    project_guid = resource.metadata.guid or (
        existing.metadata.guid if existing is not None else None
    )
    if project_guid is None:
        msg = "Project was not found for deletion"
        raise HttpNotFoundError(msg)
    await record_write_async(
        context,
        "deleted",
        lambda: client.delete_project(project_guid, **organization_options(context)),
    )


__all__ = [
    "apply_project",
    "apply_project_async",
    "delete_project",
    "delete_project_async",
    "update_project",
    "update_project_async",
]
