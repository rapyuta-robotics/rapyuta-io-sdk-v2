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

"""Shared direct-resource apply and delete outcome policies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

from rapyuta_io_sdk_v2.apply._readiness import (
    wait_for_deployment_dependencies,
    wait_for_deployment_dependencies_async,
    wait_for_resource,
    wait_for_resource_async,
)
from rapyuta_io_sdk_v2.apply.errors import (
    ApplierValidationError,
    UnsupportedResourceOperationError,
)
from rapyuta_io_sdk_v2.exceptions import (
    HttpAlreadyExistsError,
    HttpNotFoundError,
    UnauthorizedAccessError,
)
from rapyuta_io_sdk_v2.models.applier import (
    MutationAction,
    ResourceCapabilities,
    ResourceContext,
    ResourceOutcome,
    ResourceScope,
)
from rapyuta_io_sdk_v2.models.progress import MutationJournal

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.models.applier import ResourceIdentity
    from rapyuta_io_sdk_v2.models.base import SDKModel
    from rapyuta_io_sdk_v2.models.deployment import Deployment


class _ResourceLifecycle(Protocol):
    def resource_identity(
        self, *, scope: ResourceScope | None = None
    ) -> ResourceIdentity: ...

    def resource_capabilities(self) -> ResourceCapabilities: ...

    def retention_policy(self) -> str: ...

    def create_object(
        self, client: Client, *, context: ResourceContext
    ) -> SDKModel: ...

    def update_object(
        self, client: Client, *, context: ResourceContext
    ) -> SDKModel: ...

    async def create_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> SDKModel: ...

    async def update_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> SDKModel: ...

    def _delete_object(self, client: Client, *, context: ResourceContext) -> None: ...

    async def _delete_object_async(
        self, client: AsyncClient, *, context: ResourceContext
    ) -> None: ...


def _context_with_journal(context: ResourceContext) -> ResourceContext:
    """Return a local context that retains the exact caller journal, if any."""
    if context.progress is not None:
        return context
    return context.model_copy(update={"progress": MutationJournal()})


def _scope_conflicts(selected: str | None, resource: str | None) -> bool:
    return selected is not None and resource is not None and selected != resource


def _effective_context(
    resource: _ResourceLifecycle, context: ResourceContext
) -> tuple[ResourceIdentity, ResourceContext]:
    identity = resource.resource_identity(scope=context.scope)
    selected = context.scope
    if _scope_conflicts(selected.organization_guid, identity.scope.organization_guid):
        msg = "resource organization scope conflicts with the selected scope"
        raise ApplierValidationError(
            msg, category="scope_conflict", identities=(identity,)
        )
    if _scope_conflicts(selected.project_guid, identity.scope.project_guid):
        msg = "resource project scope conflicts with the selected scope"
        raise ApplierValidationError(
            msg, category="scope_conflict", identities=(identity,)
        )
    effective_scope = ResourceScope(
        organization_guid=(
            selected.organization_guid or identity.scope.organization_guid
        ),
        project_guid=selected.project_guid or identity.scope.project_guid,
        organization_short_guid=selected.organization_short_guid,
    )
    if effective_scope != selected:
        context = context.model_copy(update={"scope": effective_scope})
    return resource.resource_identity(scope=effective_scope), context


def _progress(journal: MutationJournal) -> tuple[tuple[MutationAction, ...], bool]:
    attempts = journal.snapshot()
    completed = tuple(
        attempt.action for attempt in attempts if attempt.state == "completed"
    )
    uncertain = any(attempt.state in {"uncertain", "started"} for attempt in attempts)
    return completed, uncertain


def _unsupported_policy(
    identity: ResourceIdentity,
) -> UnsupportedResourceOperationError:
    msg = f"{identity.kind} requires a specialized apply workflow"
    return UnsupportedResourceOperationError(
        msg,
        identity=identity,
        operation="apply",
    )


def _update_sync(
    resource: _ResourceLifecycle, client: Client, context: ResourceContext
) -> str:
    resource.update_object(client, context=context)
    return "updated"


async def _update_async(
    resource: _ResourceLifecycle, client: AsyncClient, context: ResourceContext
) -> str:
    await resource.update_object_async(client, context=context)
    return "updated"


def _apply_sync_policy(
    resource: _ResourceLifecycle,
    client: Client,
    context: ResourceContext,
) -> str:

    policy = resource.resource_capabilities().apply_policy
    if policy == "update_only":
        return _update_sync(resource, client, context)
    if policy not in {"create_or_update", "create_or_exists"}:
        raise _unsupported_policy(resource.resource_identity(scope=context.scope))
    return _create_sync_fallback(resource, client, context)


def _create_sync_fallback(
    resource: _ResourceLifecycle,
    client: Client,
    context: ResourceContext,
) -> str:
    policy = resource.resource_capabilities().apply_policy
    try:
        resource.create_object(client, context=context)
    except HttpAlreadyExistsError:
        if policy == "create_or_exists":
            return "exists"
        return _update_sync(resource, client, context)
    except UnauthorizedAccessError:
        if policy != "create_or_update":
            raise
        return _update_sync(resource, client, context)
    return "created"


async def _apply_async_policy(
    resource: _ResourceLifecycle,
    client: AsyncClient,
    context: ResourceContext,
) -> str:

    policy = resource.resource_capabilities().apply_policy
    if policy == "update_only":
        return await _update_async(resource, client, context)
    if policy not in {"create_or_update", "create_or_exists"}:
        raise _unsupported_policy(resource.resource_identity(scope=context.scope))
    return await _create_async_fallback(resource, client, context)


async def _create_async_fallback(
    resource: _ResourceLifecycle,
    client: AsyncClient,
    context: ResourceContext,
) -> str:
    policy = resource.resource_capabilities().apply_policy
    try:
        await resource.create_object_async(client, context=context)
    except HttpAlreadyExistsError:
        if policy == "create_or_exists":
            return "exists"
        return await _update_async(resource, client, context)
    except UnauthorizedAccessError:
        if policy != "create_or_update":
            raise
        return await _update_async(resource, client, context)
    return "created"


def _apply_outcome(
    identity: ResourceIdentity,
    status: str,
    context: ResourceContext,
) -> ResourceOutcome:
    completed, uncertain = _progress(cast("MutationJournal", context.progress))
    return ResourceOutcome(
        identity=identity,
        operation="apply",
        status=status,
        completed_actions=completed,
        write_uncertain=uncertain,
    )


def apply_resource(
    resource: _ResourceLifecycle, client: Client, *, context: ResourceContext
) -> ResourceOutcome:
    """Apply the declared create/update policy and capture journal-derived progress."""
    context = _context_with_journal(context)
    capabilities = resource.resource_capabilities()
    identity, context = _effective_context(resource, context)
    if identity.kind == "deployment":
        wait_for_deployment_dependencies(
            cast("Deployment", resource), client, context=context
        )
    status = _apply_sync_policy(resource, client, context)

    readiness_kind = capabilities.readiness_kind
    if readiness_kind is not None and status != "exists":
        wait_for_resource(
            resource,
            client,
            context=context,
            kind=readiness_kind,
        )
    return _apply_outcome(identity, status, context)


async def apply_resource_async(
    resource: _ResourceLifecycle, client: AsyncClient, *, context: ResourceContext
) -> ResourceOutcome:
    """Apply the declared policy with native asynchronous resource methods."""
    context = _context_with_journal(context)
    capabilities = resource.resource_capabilities()
    identity, context = _effective_context(resource, context)
    if identity.kind == "deployment":
        await wait_for_deployment_dependencies_async(
            cast("Deployment", resource), client, context=context
        )
    status = await _apply_async_policy(resource, client, context)

    readiness_kind = capabilities.readiness_kind
    if readiness_kind is not None and status != "exists":
        await wait_for_resource_async(
            resource,
            client,
            context=context,
            kind=readiness_kind,
        )
    return _apply_outcome(identity, status, context)


def delete_resource(
    resource: _ResourceLifecycle, client: Client, *, context: ResourceContext
) -> ResourceOutcome:
    """Apply retention and deletion outcome policy around a declared hook."""
    context = _context_with_journal(context)
    identity, context = _effective_context(resource, context)
    if resource.retention_policy() == "retain":
        return ResourceOutcome(
            identity=identity,
            operation="delete",
            status="retained",
        )
    try:
        resource._delete_object(client, context=context)  # noqa: SLF001
    except HttpNotFoundError:
        return ResourceOutcome(
            identity=identity,
            operation="delete",
            status="absent",
        )
    completed, uncertain = _progress(cast("MutationJournal", context.progress))
    return ResourceOutcome(
        identity=identity,
        operation="delete",
        status="deleted",
        completed_actions=completed,
        write_uncertain=uncertain,
    )


async def delete_resource_async(
    resource: _ResourceLifecycle, client: AsyncClient, *, context: ResourceContext
) -> ResourceOutcome:
    """Apply async retention and deletion outcome policy around a declared hook."""
    context = _context_with_journal(context)
    identity, context = _effective_context(resource, context)
    if resource.retention_policy() == "retain":
        return ResourceOutcome(
            identity=identity,
            operation="delete",
            status="retained",
        )
    try:
        await resource._delete_object_async(  # noqa: SLF001
            client, context=context
        )
    except HttpNotFoundError:
        return ResourceOutcome(
            identity=identity,
            operation="delete",
            status="absent",
        )
    completed, uncertain = _progress(cast("MutationJournal", context.progress))
    return ResourceOutcome(
        identity=identity,
        operation="delete",
        status="deleted",
        completed_actions=completed,
        write_uncertain=uncertain,
    )


__all__ = [
    "apply_resource",
    "apply_resource_async",
    "delete_resource",
    "delete_resource_async",
]
