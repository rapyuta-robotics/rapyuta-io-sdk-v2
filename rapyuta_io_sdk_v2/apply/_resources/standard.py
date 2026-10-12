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

"""Shared scope reconciliation and mutation recording for resource methods."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from typing import TYPE_CHECKING, Protocol, TypedDict, TypeVar, cast

from rapyuta_io_sdk_v2.apply.errors import ApplierValidationError
from rapyuta_io_sdk_v2.exceptions import (
    HttpAlreadyExistsError,
    HttpNotFoundError,
    MethodNotAllowedError,
    UnauthorizedAccessError,
)
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.progress import MutationJournal

if TYPE_CHECKING:
    from collections.abc import Iterator

    from rapyuta_io_sdk_v2.models.applier import MutationAction, ResourceContext
    from rapyuta_io_sdk_v2.models.utils import BaseMetadata

T = TypeVar("T")
SyncCall = Callable[[], T]
AsyncCall = Callable[[], Awaitable[T]]


class _HasMetadata(Protocol):
    metadata: BaseMetadata | None


class _OrganizationScopeOptions(TypedDict, total=False):
    organization_guid: str


class _ProjectScopeOptions(_OrganizationScopeOptions, total=False):
    project_guid: str


def _scope_conflicts(selected: str | None, metadata: str | None) -> bool:
    return selected is not None and metadata is not None and selected != metadata


def _validate_scope_compatibility(
    metadata: BaseMetadata,
    context: ResourceContext,
    *,
    include_organization: bool,
    include_project: bool,
) -> None:
    if include_organization and _scope_conflicts(
        context.scope.organization_guid, metadata.organization_guid
    ):
        msg = "resource organization scope conflicts with the selected scope"
        raise ApplierValidationError(msg, category="scope_conflict")
    if include_project and _scope_conflicts(
        context.scope.project_guid, metadata.project_guid
    ):
        msg = "resource project scope conflicts with the selected scope"
        raise ApplierValidationError(msg, category="scope_conflict")


def organization_options(context: ResourceContext) -> _OrganizationScopeOptions:
    """Build organization-only options without changing client configuration."""
    options: _OrganizationScopeOptions = {}
    if context.scope.organization_guid is not None:
        options["organization_guid"] = context.scope.organization_guid
    return options


def project_options(context: ResourceContext) -> _ProjectScopeOptions:
    """Build scoped endpoint options without passing duplicate context flags."""
    options: _ProjectScopeOptions = {**organization_options(context)}
    if context.scope.project_guid is not None:
        options["project_guid"] = context.scope.project_guid
    return options


def scoped_copy[T: SDKModel](
    resource: T,
    context: ResourceContext,
    *,
    include_organization: bool = True,
    include_project: bool = True,
) -> T:
    """Copy a typed resource after checking its selected routing scope."""
    data = cast("_HasMetadata", resource)
    if data.metadata is None:
        return resource.model_copy(deep=True)
    _validate_scope_compatibility(
        data.metadata,
        context,
        include_organization=include_organization,
        include_project=include_project,
    )
    updates: dict[str, object] = {}
    if include_organization and context.scope.organization_guid is not None:
        updates["organization_guid"] = context.scope.organization_guid
    if include_project and context.scope.project_guid is not None:
        updates["project_guid"] = context.scope.project_guid
    metadata = data.metadata.model_copy(deep=True, update=updates)
    return resource.model_copy(deep=True, update={"metadata": metadata})


def scoped_context(
    resource: SDKModel, context: ResourceContext, *, include_project: bool = True
) -> ResourceContext:
    """Reconcile metadata and context before direct lookups or writes."""
    metadata = cast("_HasMetadata", resource).metadata
    if metadata is None:
        return context
    _validate_scope_compatibility(
        metadata, context, include_organization=True, include_project=include_project
    )
    updates: dict[str, object] = {
        "organization_guid": (
            context.scope.organization_guid or metadata.organization_guid
        )
    }
    if include_project:
        updates["project_guid"] = context.scope.project_guid or metadata.project_guid
    scope = context.scope.model_copy(update=updates)
    return context.model_copy(update={"scope": scope})


@contextmanager
def _recorded_write(context: ResourceContext, action: MutationAction) -> Iterator[None]:
    journal = context.progress or MutationJournal()
    sequence = journal.begin(action)
    try:
        yield
    except (
        HttpAlreadyExistsError,
        HttpNotFoundError,
        MethodNotAllowedError,
        UnauthorizedAccessError,
    ):
        journal.reject(sequence)
        raise
    except BaseException:
        journal.mark_uncertain(sequence)
        raise
    journal.complete(sequence)


def record_write[T](
    context: ResourceContext, action: MutationAction, call: SyncCall[T]
) -> T:
    """Instrument one synchronous write without retaining its arguments."""
    with _recorded_write(context, action):
        return call()


async def record_write_async[T](
    context: ResourceContext, action: MutationAction, call: AsyncCall[T]
) -> T:
    """Instrument one native asynchronous write without retaining its arguments."""
    with _recorded_write(context, action):
        return await call()


__all__ = [
    "organization_options",
    "project_options",
    "record_write",
    "record_write_async",
    "scoped_context",
    "scoped_copy",
]
