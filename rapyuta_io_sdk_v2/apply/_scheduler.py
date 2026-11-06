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

"""Bounded graph scheduler for paired resource lifecycle operations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from graphlib import TopologicalSorter
from typing import TYPE_CHECKING, Literal, cast

from rapyuta_io_sdk_v2.apply.errors import (
    ApplierExecutionError,
    ReadinessError,
    UnsupportedResourceOperationError,
)
from rapyuta_io_sdk_v2.models.applier import (
    ApplierResult,
    OperationFailure,
    ReadinessOptions,
    ResourceContext,
    ResourceOutcome,
    ResourceScope,
    SourceLocation,
)
from rapyuta_io_sdk_v2.models.progress import MutationJournal

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from rapyuta_io_sdk_v2.apply._loader import PreparedResource
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.models.applier import ResourceIdentity
    from rapyuta_io_sdk_v2.models.progress import MutationAction
    from rapyuta_io_sdk_v2.models.resource import Resource

Operation = Literal["apply", "delete"]
_Captured = ResourceOutcome | BaseException


@dataclass(frozen=True, slots=True)
class _ExecutionOptions:
    scope: ResourceScope
    readiness: ReadinessOptions
    operation: Operation = "apply"
    workers: int = 1
    publish: Callable[[ApplierResult], None] | None = None


@dataclass(slots=True)
class _SchedulerState:
    resources: Sequence[PreparedResource]
    edges: Sequence[tuple[ResourceIdentity, ResourceIdentity]]
    options: _ExecutionOptions
    client: Client | AsyncClient
    journals: list[MutationJournal]
    outcomes: list[ResourceOutcome | None]
    failures: list[OperationFailure]


@dataclass(frozen=True, slots=True)
class _ResourceCall:
    operation: Operation
    context: ResourceContext


def _safe_failure(
    exception: BaseException, *, operation: Operation
) -> OperationFailure:
    """Build a result-safe failure that never embeds arbitrary response bodies."""
    category = (
        "cancelled" if isinstance(exception, asyncio.CancelledError) else "lifecycle"
    )
    stage = "readiness" if isinstance(exception, ReadinessError) else operation
    return OperationFailure(
        category=category,
        stage=stage,
        message=f"{operation} raised {type(exception).__name__}",
        exception_type=type(exception).__name__,
    )


def _completed_actions(
    journal: MutationJournal,
) -> tuple[tuple[MutationAction, ...], bool]:
    attempts = journal.snapshot()
    completed = tuple(item.action for item in attempts if item.state == "completed")
    uncertain = any(item.state in {"started", "uncertain"} for item in attempts)
    return completed, uncertain


def _snapshot_outcome(
    outcome: ResourceOutcome,
    *,
    source: SourceLocation,
    journal: MutationJournal,
) -> ResourceOutcome:
    completed, uncertain = _completed_actions(journal)
    return outcome.model_copy(
        update={
            "source": source,
            "completed_actions": completed,
            "write_uncertain": uncertain,
        }
    )


def _index_by_identity(
    resources: Sequence[PreparedResource],
) -> dict[ResourceIdentity, int]:
    return {item.identity: index for index, item in enumerate(resources)}


def _dependency_map(
    resources: Sequence[PreparedResource],
    edges: Sequence[tuple[ResourceIdentity, ResourceIdentity]],
    *,
    operation: Operation,
) -> tuple[TopologicalSorter, dict[ResourceIdentity, int]]:
    positions = _index_by_identity(resources)
    predecessors: dict[int, set[int]] = {
        index: set() for index in range(len(resources))
    }
    for prerequisite, dependent in edges:
        before, after = (
            (prerequisite, dependent)
            if operation == "apply"
            else (dependent, prerequisite)
        )
        predecessors[positions[after]].add(positions[before])
    return TopologicalSorter(predecessors), positions


def _operation_method(
    resource: Resource,
    client: Client,
    call: _ResourceCall,
) -> ResourceOutcome:
    if call.operation == "apply":
        return resource.apply(client, context=call.context)
    return resource.delete_object(client, context=call.context)


async def _operation_method_async(
    resource: Resource,
    client: AsyncClient,
    call: _ResourceCall,
) -> ResourceOutcome:
    if call.operation == "apply":
        return await resource.apply_async(client, context=call.context)
    return await resource.delete_object_async(client, context=call.context)


def _context(
    item: PreparedResource,
    options: _ExecutionOptions,
    *,
    journal: MutationJournal,
) -> ResourceContext:
    identity_scope = item.identity.scope
    organization_guid = (
        identity_scope.organization_guid or options.scope.organization_guid
    )
    if item.identity.kind == "organization":
        organization_guid = item.identity.guid or organization_guid
    project_guid = identity_scope.project_guid or options.scope.project_guid
    effective_scope = ResourceScope(
        organization_guid=organization_guid,
        project_guid=project_guid,
        organization_short_guid=options.scope.organization_short_guid,
    )
    return ResourceContext(
        scope=effective_scope,
        readiness=options.readiness,
        progress=journal,
    )


def _preflight(resources: Sequence[PreparedResource], operation: Operation) -> None:
    for item in resources:
        _preflight_item(item, operation)


def _preflight_item(item: PreparedResource, operation: Operation) -> None:
    resource = cast("Resource", item.resource)
    capabilities = resource.resource_capabilities()
    if operation == "delete":
        if not capabilities.delete and resource.retention_policy() != "retain":
            msg = f"{item.identity.kind} does not support delete"
            raise UnsupportedResourceOperationError(
                msg,
                identity=item.identity,
                operation="delete",
            )
        return
    if capabilities.apply_policy == "grant":
        return
    if not capabilities.create and not capabilities.update:
        msg = f"{item.identity.kind} does not support apply"
        raise UnsupportedResourceOperationError(
            msg,
            identity=item.identity,
            operation="apply",
        )


def _failure_snapshot(
    item: PreparedResource,
    exception: BaseException,
    *,
    operation: Operation,
    journal: MutationJournal,
) -> tuple[ResourceOutcome, OperationFailure]:
    failure = _safe_failure(exception, operation=operation)
    completed, uncertain = _completed_actions(journal)
    cancelled = isinstance(exception, asyncio.CancelledError)
    outcome = ResourceOutcome(
        identity=item.identity,
        source=item.source,
        operation=operation,
        status="not_completed" if cancelled else "failed",
        completed_actions=completed,
        failure=failure,
        incomplete_reason="cancelled" if cancelled else None,
        write_uncertain=uncertain,
    )
    return outcome, failure


def _execute_sync_resource(
    item: PreparedResource,
    client: Client,
    *,
    options: _ExecutionOptions,
    journal: MutationJournal,
) -> tuple[ResourceOutcome, OperationFailure | None]:
    operation = options.operation
    try:
        context = _context(item, options, journal=journal)
        outcome = _operation_method(
            cast("Resource", item.resource), client, _ResourceCall(operation, context)
        )
    except Exception as exception:  # noqa: BLE001  # Convert per-resource failures.
        return _failure_snapshot(item, exception, operation=operation, journal=journal)
    return _snapshot_outcome(outcome, source=item.source, journal=journal), None


def _pending_outcome(
    item: PreparedResource,
    operation: Operation,
    *,
    reason: Literal["blocked", "not_started"],
) -> ResourceOutcome:
    return ResourceOutcome(
        identity=item.identity,
        source=item.source,
        operation=operation,
        status="not_completed",
        incomplete_reason=reason,
    )


def _scheduler_state(
    resources: Sequence[PreparedResource],
    edges: Sequence[tuple[ResourceIdentity, ResourceIdentity]],
    client: Client | AsyncClient,
    *,
    options: _ExecutionOptions,
) -> _SchedulerState:
    _preflight(resources, options.operation)
    return _SchedulerState(
        resources=resources,
        edges=edges,
        options=options,
        client=client,
        journals=[MutationJournal() for _ in resources],
        outcomes=[None] * len(resources),
        failures=[],
    )


def execute_sync(
    resources: Sequence[PreparedResource],
    edges: Sequence[tuple[ResourceIdentity, ResourceIdentity]],
    client: Client,
    *,
    options: _ExecutionOptions,
) -> ApplierResult:
    """Execute sync resources in topological cohorts using the supplied client."""
    state = _scheduler_state(resources, edges, client, options=options)
    _execute_sync_cohorts(state)
    return _finish_result(state)


def _execute_sync_cohorts(state: _SchedulerState) -> None:
    resources = state.resources
    edges = state.edges
    options = state.options
    client = cast("Client", state.client)
    operation = options.operation
    sorter, _positions = _dependency_map(resources, edges, operation=operation)
    sorter.prepare()
    while sorter.is_active():
        cohort = sorter.get_ready()
        cohort_failed = False
        for index in cohort:
            state.outcomes[index], failure = _execute_sync_resource(
                resources[index],
                client,
                options=options,
                journal=state.journals[index],
            )
            if failure is not None:
                state.failures.append(failure)
                cohort_failed = True
                break
        if cohort_failed:
            break
        sorter.done(*cohort)


async def _capture(
    item: PreparedResource,
    *,
    client: AsyncClient,
    options: _ExecutionOptions,
    journal: MutationJournal,
) -> _Captured:
    try:
        context = _context(item, options, journal=journal)
        outcome = await _operation_method_async(
            cast("Resource", item.resource),
            client,
            _ResourceCall(options.operation, context),
        )
        return _snapshot_outcome(outcome, source=item.source, journal=journal)
    except BaseException as exception:  # noqa: BLE001  # Preserve cancellation per resource.
        return exception


async def execute_async(
    resources: Sequence[PreparedResource],
    edges: Sequence[tuple[ResourceIdentity, ResourceIdentity]],
    client: AsyncClient,
    *,
    options: _ExecutionOptions,
) -> ApplierResult:
    """Execute native async resource operations with bounded cohort workers."""
    state = _scheduler_state(resources, edges, client, options=options)
    try:
        await _execute_async_cohorts(state)
    except asyncio.CancelledError:
        _finish_result(state, raise_on_failure=False)
        raise
    return _finish_result(state)


async def _execute_async_cohorts(state: _SchedulerState) -> None:
    sorter, _positions = _dependency_map(
        state.resources, state.edges, operation=state.options.operation
    )
    sorter.prepare()
    while sorter.is_active():
        cohort = list(sorter.get_ready())
        if await _run_async_cohort(cohort, state):
            break
        sorter.done(*cohort)


async def _run_async_cohort(cohort: list[int], state: _SchedulerState) -> bool:
    workers = state.options.workers
    for start in range(0, len(cohort), workers):
        chunk = cohort[start : start + workers]
        captured = await _run_async_chunk(chunk, state)
        if _store_async_chunk(chunk, captured, state):
            return True
    return False


def _store_async_chunk(
    chunk: list[int], captured: list[_Captured], state: _SchedulerState
) -> bool:
    failed = False
    for index, item in zip(chunk, captured, strict=True):
        failed = _store_capture(index, item, state) or failed
    return failed


async def _run_async_chunk(chunk: list[int], state: _SchedulerState) -> list[_Captured]:
    tasks: list[asyncio.Task[_Captured]] = []
    try:
        async with asyncio.TaskGroup() as task_group:
            tasks = _create_async_tasks(chunk, state, task_group)
            await _cancel_siblings_after_failure(tasks)
        return [_task_capture(task) for task in tasks]
    except asyncio.CancelledError:
        await _settle_cancelled_tasks(tasks)
        for index, task in zip(chunk, tasks, strict=False):
            captured = _task_capture(task)
            _store_capture(index, captured, state)
        raise


def _create_async_tasks(
    chunk: list[int],
    state: _SchedulerState,
    task_group: asyncio.TaskGroup,
) -> list[asyncio.Task[_Captured]]:
    return [
        task_group.create_task(
            _capture(
                state.resources[index],
                client=cast("AsyncClient", state.client),
                options=state.options,
                journal=state.journals[index],
            )
        )
        for index in chunk
    ]


async def _cancel_siblings_after_failure(
    tasks: list[asyncio.Task[_Captured]],
) -> None:
    pending = set(tasks)
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        if any(_task_failed(task) for task in done):
            for sibling in pending:
                sibling.cancel()
            return


def _task_capture(task: asyncio.Task[_Captured]) -> _Captured:
    if task.cancelled():
        return asyncio.CancelledError()
    return task.result()


def _task_failed(task: asyncio.Task[_Captured]) -> bool:
    return not isinstance(_task_capture(task), ResourceOutcome)


async def _settle_cancelled_tasks(tasks: list[asyncio.Task[_Captured]]) -> None:
    while tasks and not all(task.done() for task in tasks):
        try:
            await asyncio.shield(asyncio.gather(*tasks, return_exceptions=True))
        except asyncio.CancelledError:
            continue


def _finish_result(
    state: _SchedulerState,
    *,
    raise_on_failure: bool = True,
) -> ApplierResult:
    operation = state.options.operation
    result = _result(state.resources, state.outcomes, operation, edges=state.edges)
    if state.options.publish is not None:
        state.options.publish(result)
    if raise_on_failure and not result.successful:
        msg = f"{operation} did not complete successfully"
        raise ApplierExecutionError(
            msg,
            result=result,
            causes=state.failures,
        )
    return result


def _store_capture(index: int, captured: _Captured, state: _SchedulerState) -> bool:
    item = state.resources[index]
    journal = state.journals[index]
    if isinstance(captured, ResourceOutcome):
        state.outcomes[index] = _snapshot_outcome(
            captured, source=item.source, journal=journal
        )
        return False
    outcome, failure = _failure_snapshot(
        item, captured, operation=state.options.operation, journal=journal
    )
    state.failures.append(failure)
    state.outcomes[index] = outcome
    return True


def _mark_unstarted(
    resources: Sequence[PreparedResource],
    outcomes: list[ResourceOutcome | None],
    operation: Operation,
    *,
    failed: bool,
    edges: Sequence[tuple[ResourceIdentity, ResourceIdentity]] = (),
) -> None:
    dependents = _dependent_indexes(resources, edges, operation)
    blocked = _blocked_indexes(outcomes, dependents)
    for index, item in enumerate(resources):
        if outcomes[index] is None:
            outcomes[index] = _pending_outcome(
                item,
                operation,
                reason="blocked" if failed and index in blocked else "not_started",
            )


def _dependent_indexes(
    resources: Sequence[PreparedResource],
    edges: Sequence[tuple[ResourceIdentity, ResourceIdentity]],
    operation: Operation,
) -> dict[int, set[int]]:
    positions = _index_by_identity(resources)
    dependents: dict[int, set[int]] = {index: set() for index in range(len(resources))}
    for prerequisite, dependent in edges:
        before, after = (
            (prerequisite, dependent)
            if operation == "apply"
            else (dependent, prerequisite)
        )
        dependents[positions[before]].add(positions[after])
    return dependents


def _blocked_indexes(
    outcomes: list[ResourceOutcome | None], dependents: dict[int, set[int]]
) -> set[int]:
    blocked: set[int] = set()
    pending = [
        index
        for index, outcome in enumerate(outcomes)
        if outcome is not None and outcome.status in {"failed", "not_completed"}
    ]
    while pending:
        for dependent in dependents[pending.pop()]:
            if dependent not in blocked:
                blocked.add(dependent)
                pending.append(dependent)
    return blocked


def _result(
    resources: Sequence[PreparedResource],
    outcomes: list[ResourceOutcome | None],
    operation: Operation,
    *,
    edges: Sequence[tuple[ResourceIdentity, ResourceIdentity]],
) -> ApplierResult:
    _mark_unstarted(
        resources,
        outcomes,
        operation,
        failed=any(
            outcome is not None and outcome.status in {"failed", "not_completed"}
            for outcome in outcomes
        ),
        edges=edges,
    )
    return ApplierResult(
        operation=operation,
        outcomes=tuple(cast("ResourceOutcome", outcome) for outcome in outcomes),
    )


__all__ = ["execute_async", "execute_sync"]
