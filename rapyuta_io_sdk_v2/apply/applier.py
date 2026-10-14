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

"""Call-time-client sync and async facades for prepared resource collections."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from threading import Lock
from typing import TYPE_CHECKING, Literal

from pydantic import ValidationError

from rapyuta_io_sdk_v2.apply._graph import prepare_dependency_graph
from rapyuta_io_sdk_v2.apply._loader import (
    PreparedCollection,
    PreparedResource,
    prepare_source,
)
from rapyuta_io_sdk_v2.apply._scheduler import (
    _ExecutionOptions,
    execute_async,
    execute_sync,
)
from rapyuta_io_sdk_v2.apply.errors import (
    ApplierUsageError,
    ApplierValidationError,
    MissingResourceContextError,
    UnsupportedResourceOperationError,
)
from rapyuta_io_sdk_v2.async_client import AsyncClient as NativeAsyncClient
from rapyuta_io_sdk_v2.client import Client as SyncClient
from rapyuta_io_sdk_v2.models.applier import (
    ApplierOptions,
    ApplierResult,
    InspectionResult,
    RenderedDocument,
    ResourceIdentity,
    ResourceOutcome,
    ResourceScope,
)
from rapyuta_io_sdk_v2.models.secret import SecretCreate
from rapyuta_io_sdk_v2.models.usergroup import UserGroupCreate

if TYPE_CHECKING:
    from collections.abc import Iterator

    from rapyuta_io_sdk_v2.apply.source import ManifestSource
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client

Operation = Literal["apply", "delete"]
_ORG_SCOPED = frozenset(
    {"project", "usergroup", "role", "rolebinding", "serviceaccount"}
)
_PROJECT_SCOPED = frozenset(
    {"package", "deployment", "disk", "network", "staticroute", "secret"}
)
_ORGANIZATION_REQUIRED = _ORG_SCOPED | _PROJECT_SCOPED | {"organization"}


def _copy_collection(source: PreparedCollection) -> tuple[PreparedResource, ...]:
    """Build per-call model copies while retaining immutable source attribution."""
    return tuple(
        replace(
            item,
            resource=deepcopy(item.resource),
            source_data=deepcopy(item.source_data),
        )
        for item in source.resources
    )


def _with_resource_graph(
    resources: tuple[PreparedResource, ...], scope: ResourceScope
) -> tuple[
    tuple[PreparedResource, ...],
    tuple[tuple[ResourceIdentity, ResourceIdentity], ...],
    object,
]:
    nodes = []
    for item in resources:
        resource = item.resource
        identity = resource.resource_identity(scope=scope)
        dependencies = resource.resource_dependencies(scope=scope)
        nodes.append((identity, dependencies))
    plan = prepare_dependency_graph(nodes, scope=scope)
    prepared = tuple(
        replace(
            item,
            identity=plan.dependency_graph.managed[index],
            dependencies=item.resource.resource_dependencies(scope=scope),
        )
        for index, item in enumerate(resources)
    )
    return prepared, plan.dependency_graph.edges, plan


def _validate_scope_conflicts(
    resources: tuple[PreparedResource, ...], scope: ResourceScope
) -> None:
    for item in resources:
        identity = item.identity
        if _organization_scope_conflicts(identity, scope):
            msg = "resource organization conflicts with the selected scope"
            raise ApplierValidationError(
                msg,
                source=item.source,
                category="scope_conflict",
                identities=(identity,),
            )
        if _project_scope_conflicts(identity, scope):
            msg = "resource project conflicts with the selected scope"
            raise ApplierValidationError(
                msg,
                source=item.source,
                category="scope_conflict",
                identities=(identity,),
            )


def _organization_scope_conflicts(
    identity: ResourceIdentity, scope: ResourceScope
) -> bool:
    return (
        identity.kind in _ORG_SCOPED | _PROJECT_SCOPED
        and scope.organization_guid is not None
        and identity.scope.organization_guid is not None
        and scope.organization_guid != identity.scope.organization_guid
    )


def _project_scope_conflicts(identity: ResourceIdentity, scope: ResourceScope) -> bool:
    return (
        identity.kind in _PROJECT_SCOPED
        and scope.project_guid is not None
        and identity.scope.project_guid is not None
        and scope.project_guid != identity.scope.project_guid
    )


def _validate_organization_target(item: PreparedResource) -> None:
    if item.identity.kind == "organization" and item.identity.guid is None:
        msg = "Organization apply requires metadata.guid"
        raise ApplierValidationError(
            msg,
            source=item.source,
            category="required_guid",
            identities=(item.identity,),
        )


def _validate_apply_payloads(resources: tuple[PreparedResource, ...]) -> None:
    """Revalidate apply-specific targets and payloads before any write."""
    for item in resources:
        _validate_organization_target(item)
        data = item.resource.model_dump(mode="python", by_alias=True)
        try:
            if item.identity.kind == "secret":
                SecretCreate.model_validate(data)
            elif item.identity.kind == "usergroup":
                UserGroupCreate.model_validate(data)
        except ValidationError as exception:
            msg = f"{item.identity.kind} is not a valid creation payload"
            raise ApplierValidationError(
                msg,
                source=item.source,
                category="create_payload",
                identities=(item.identity,),
            ) from exception


def _client_scope(
    client: Client | AsyncClient, options: ApplierOptions
) -> ResourceScope:
    configuration = client.config
    configured_organization = configuration.organization_guid
    configured_project = configuration.project_guid
    pinned = options.scope
    if (
        pinned.organization_guid is not None
        and configured_organization is not None
        and pinned.organization_guid != configured_organization
    ):
        msg = "selected organization scope conflicts with the supplied client"
        raise ApplierValidationError(
            msg,
            category="scope_conflict",
        )
    if (
        pinned.project_guid is not None
        and configured_project is not None
        and pinned.project_guid != configured_project
    ):
        msg = "selected project scope conflicts with the supplied client"
        raise ApplierValidationError(
            msg,
            category="scope_conflict",
        )
    return ResourceScope(
        organization_guid=pinned.organization_guid or configured_organization,
        project_guid=pinned.project_guid or configured_project,
        organization_short_guid=pinned.organization_short_guid,
    )


def _require_client_context(
    resources: tuple[PreparedResource, ...],
    client: Client | AsyncClient,
    scope: ResourceScope,
    *,
    operation: Operation,
) -> None:
    if not client.config.auth_token or not client.config.auth_token.strip():
        msg = "the supplied client has no configured authentication token"
        raise MissingResourceContextError(
            msg,
            operation=operation,
            required_context=("auth_token",),
        )
    for item in resources:
        identity = item.identity
        required = _required_context(identity, scope)
        if required:
            msg = f"{identity.kind} operation requires routing context"
            raise MissingResourceContextError(
                msg,
                resource=identity,
                operation=operation,
                required_context=required,
            )


def _required_context(
    identity: ResourceIdentity, scope: ResourceScope
) -> tuple[str, ...]:
    organization_guid = identity.scope.organization_guid or scope.organization_guid
    if identity.kind == "organization":
        organization_guid = identity.guid or organization_guid
    project_guid = identity.scope.project_guid or scope.project_guid
    required: list[str] = []
    if identity.kind in _ORGANIZATION_REQUIRED and organization_guid is None:
        required.append("organization_guid")
    if identity.kind in _PROJECT_SCOPED and project_guid is None:
        required.append("project_guid")
    return tuple(required)


def _preview(
    resources: tuple[PreparedResource, ...],
    operation: Operation,
) -> ApplierResult:
    outcomes: list[ResourceOutcome] = []
    for item in resources:
        capabilities = item.resource.resource_capabilities()
        retained = item.resource.retention_policy() == "retain"
        if operation == "apply":
            _validate_apply_payloads((item,))
            policy = capabilities.apply_policy
            planned = "update" if policy == "update_only" else policy
        elif retained:
            outcomes.append(
                ResourceOutcome(
                    identity=item.identity,
                    source=item.source,
                    operation="delete",
                    status="retained",
                )
            )
            continue
        else:
            if not capabilities.delete:
                msg = f"{item.identity.kind} does not support delete"
                raise UnsupportedResourceOperationError(
                    msg,
                    identity=item.identity,
                    operation="delete",
                )
            planned = "revoke" if item.identity.kind == "rolebinding" else "delete"
        outcomes.append(
            ResourceOutcome(
                identity=item.identity,
                source=item.source,
                operation=operation,
                status="planned",
                planned_action=planned,
            )
        )
    return ApplierResult(operation=operation, dry_run=True, outcomes=tuple(outcomes))


def _require_sync_loop() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    msg = "synchronous Applier cannot run inside an active event loop"
    raise ApplierUsageError(msg)


class _PreparedFacade:
    """Local, client-free preparation shared by both public facades."""

    def __init__(
        self, source: ManifestSource, options: ApplierOptions | None = None
    ) -> None:
        self.options = options or ApplierOptions()
        self._base = prepare_source(source, self.options.scope)
        self._prepared, self._edges, self._plan = _with_resource_graph(
            _copy_collection(self._base), self.options.scope
        )
        self._busy_lock = Lock()
        self.last_result: ApplierResult | None = None

    def inspect(self) -> InspectionResult:
        """Return independent model copies and offline graph metadata."""
        return InspectionResult(
            resource_identities=tuple(item.identity for item in self._prepared),
            resolved_manifests=tuple(
                deepcopy(item.resource) for item in self._prepared
            ),
            rendered_documents=tuple(
                RenderedDocument(source=item.source, data=deepcopy(item.source_data))
                for item in self._prepared
            ),
            dependency_graph=self._plan.dependency_graph,
        )

    def _for_scope(
        self, scope: ResourceScope
    ) -> tuple[
        tuple[PreparedResource, ...],
        tuple[tuple[ResourceIdentity, ResourceIdentity], ...],
        object,
    ]:
        prepared, edges, plan = _with_resource_graph(
            _copy_collection(self._base), scope
        )
        _validate_scope_conflicts(prepared, scope)
        return prepared, edges, plan

    def _preview(self, operation: Operation) -> ApplierResult:
        self._acquire()
        try:
            resources, _edges, _plan = self._for_scope(self.options.scope)
            result = _preview(resources, operation)
            self.last_result = result
            return result
        finally:
            self._release()

    def _acquire(self) -> None:
        if not self._busy_lock.acquire(blocking=False):
            msg = "this applier already has an active operation"
            raise ApplierUsageError(msg)

    def _release(self) -> None:
        self._busy_lock.release()

    def _publish(self, result: ApplierResult) -> None:
        self.last_result = result

    @contextmanager
    def _live_execution(
        self, client: Client | AsyncClient, operation: Operation, *, workers: int = 1
    ) -> Iterator[
        tuple[
            tuple[PreparedResource, ...],
            tuple[tuple[ResourceIdentity, ResourceIdentity], ...],
            _ExecutionOptions,
        ]
    ]:
        self._acquire()
        try:
            scope = _client_scope(client, self.options)
            resources, edges, _plan = self._for_scope(scope)
            if operation == "apply":
                _validate_apply_payloads(resources)
            _require_client_context(resources, client, scope, operation=operation)
            yield (
                resources,
                edges,
                _ExecutionOptions(
                    scope=scope,
                    readiness=self.options.readiness,
                    operation=operation,
                    workers=workers,
                    publish=self._publish,
                ),
            )
        finally:
            self._release()


class Applier(_PreparedFacade):
    """Synchronous reusable resource applier using caller-owned Clients."""

    def apply(
        self, client: Client | None = None, *, dry_run: bool = False
    ) -> ApplierResult:
        """Apply the prepared collection or return a client-free plan."""
        _require_sync_loop()
        if dry_run:
            return self._preview("apply")
        return self._run(client, operation="apply")

    def delete(
        self, client: Client | None = None, *, dry_run: bool = False
    ) -> ApplierResult:
        """Delete managed resources in reverse dependency order."""
        _require_sync_loop()
        if dry_run:
            return self._preview("delete")
        return self._run(client, operation="delete")

    def _run(self, client: Client | None, *, operation: Operation) -> ApplierResult:
        if not self._base.resources:
            result = ApplierResult(operation=operation)
            self.last_result = result
            return result
        if client is None:
            msg = "a configured Client must be supplied to the live operation"
            raise MissingResourceContextError(
                msg,
                operation=operation,
                required_context=("client",),
            )
        if not isinstance(client, SyncClient):
            msg = "sync Applier requires a rapyuta_io_sdk_v2 Client"
            raise ApplierUsageError(msg)
        with self._live_execution(client, operation) as (resources, edges, options):
            return execute_sync(resources, edges, client, options=options)


class AsyncApplier(_PreparedFacade):
    """Native asynchronous reusable applier using caller-owned AsyncClients."""

    async def apply(
        self, client: AsyncClient | None = None, *, dry_run: bool = False
    ) -> ApplierResult:
        """Apply asynchronously or return a local client-free plan."""
        if dry_run:
            return self._preview("apply")
        return await self._run(client, operation="apply")

    async def delete(
        self, client: AsyncClient | None = None, *, dry_run: bool = False
    ) -> ApplierResult:
        """Delete asynchronously in reverse dependency order."""
        if dry_run:
            return self._preview("delete")
        return await self._run(client, operation="delete")

    async def _run(
        self, client: AsyncClient | None, *, operation: Operation
    ) -> ApplierResult:
        if not self._base.resources:
            result = ApplierResult(operation=operation)
            self.last_result = result
            return result
        if client is None:
            msg = "a configured AsyncClient must be supplied to the live operation"
            raise MissingResourceContextError(
                msg,
                operation=operation,
                required_context=("client",),
            )
        if not isinstance(client, NativeAsyncClient):
            msg = "AsyncApplier requires a rapyuta_io_sdk_v2 AsyncClient"
            raise ApplierUsageError(msg)
        with self._live_execution(client, operation, workers=self.options.workers) as (
            resources,
            edges,
            options,
        ):
            return await execute_async(resources, edges, client, options=options)


__all__ = ["Applier", "AsyncApplier"]
