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

"""Exact role-binding grant lookup and creation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rapyuta_io_sdk_v2.apply._lifecycle import (
    _apply_outcome,
    _context_with_journal,
    _effective_context,
)
from rapyuta_io_sdk_v2.apply._resources.standard import (
    organization_options,
    record_write,
    record_write_async,
)
from rapyuta_io_sdk_v2.apply.errors import ApplierValidationError
from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError
from rapyuta_io_sdk_v2.models.rolebinding import (
    BulkRoleBindingUpdate,
    RoleBinding,
)

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client
    from rapyuta_io_sdk_v2.models.applier import ResourceContext, ResourceOutcome


@dataclass(frozen=True, slots=True)
class _RoleBindingLookup:
    binding: RoleBinding
    context: ResourceContext
    client: Client | AsyncClient


def _role_guid_for_name(
    client: Client, role_name: str, context: ResourceContext
) -> str | None:
    try:
        return client.get_role(role_name, **organization_options(context)).metadata.guid
    except HttpNotFoundError:
        return None


async def _role_guid_for_name_async(
    client: AsyncClient, role_name: str, context: ResourceContext
) -> str | None:
    try:
        role = await client.get_role(role_name, **organization_options(context))
    except HttpNotFoundError:
        return None
    else:
        return role.metadata.guid


def _same_selector(expected: str | None, actual: str | None) -> bool:
    return expected is None or expected == actual


def _matches(
    requested: RoleBinding,
    candidate: RoleBinding,
    *,
    resolved_role_guid: str | None = None,
) -> bool:
    expected = requested.spec
    actual = candidate.spec
    role_match = _same_selector(expected.role_ref.name, actual.role_ref.name)
    role_guid = actual.role_ref.guid or resolved_role_guid
    role_match = role_match and _same_selector(expected.role_ref.guid, role_guid)

    subject_match = (
        _same_selector(expected.subject.kind, actual.subject.kind)
        and _same_selector(expected.subject.name, actual.subject.name)
        and _same_selector(expected.subject.guid, actual.subject.guid)
    )
    domain_match = (
        _same_selector(expected.domain.kind, actual.domain.kind)
        and _same_selector(expected.domain.name, actual.domain.name)
        and _same_selector(expected.domain.guid, actual.domain.guid)
    )
    return role_match and subject_match and domain_match


def _lookup_filters(binding: RoleBinding) -> dict[str, list[str]]:
    role_ref = binding.spec.role_ref
    subject = binding.spec.subject
    domain = binding.spec.domain
    selectors = (
        ("role_names", role_ref.name),
        ("subject_names", subject.name),
        ("subject_guids", subject.guid),
        ("subject_kinds", subject.kind),
        ("domain_names", domain.name),
        ("domain_guids", domain.guid),
        ("domain_kinds", domain.kind),
    )
    return {key: [value] for key, value in selectors if value is not None}


def _ambiguous(binding: RoleBinding) -> ApplierValidationError:
    return ApplierValidationError(
        "RoleBinding lookup returned multiple exact grants",
        category="ambiguous",
        identities=(binding.resource_identity(),),
    )


def _identity_mismatch(
    binding: RoleBinding, message: str, *, context: ResourceContext
) -> ApplierValidationError:
    return ApplierValidationError(
        message,
        category="identity_mismatch",
        identities=(binding.resource_identity(scope=context.scope),),
    )


def _verify_rolebinding_guid(
    lookup: _RoleBindingLookup,
    found: RoleBinding,
) -> RoleBinding:
    binding = lookup.binding
    client = lookup.client
    role_guid = None
    if binding.spec.role_ref.guid is not None and found.spec.role_ref.guid is None:
        if found.spec.role_ref.name is None:
            msg = "RoleBinding GUID response cannot verify the requested role"
            raise _identity_mismatch(binding, msg, context=lookup.context)
        role_guid = _role_guid_for_name(
            client, found.spec.role_ref.name, lookup.context
        )
    if not _matches(binding, found, resolved_role_guid=role_guid):
        msg = "RoleBinding GUID resolves to a different grant"
        raise _identity_mismatch(binding, msg, context=lookup.context)
    return found


async def _verify_rolebinding_guid_async(
    lookup: _RoleBindingLookup,
    found: RoleBinding,
) -> RoleBinding:
    binding = lookup.binding
    client = lookup.client
    role_guid = None
    if binding.spec.role_ref.guid is not None and found.spec.role_ref.guid is None:
        if found.spec.role_ref.name is None:
            msg = "RoleBinding GUID response cannot verify the requested role"
            raise _identity_mismatch(binding, msg, context=lookup.context)
        role_guid = await _role_guid_for_name_async(
            client, found.spec.role_ref.name, lookup.context
        )
    if not _matches(binding, found, resolved_role_guid=role_guid):
        msg = "RoleBinding GUID resolves to a different grant"
        raise _identity_mismatch(binding, msg, context=lookup.context)
    return found


def _next_continuation(
    token: int | None, seen: set[int], lookup: _RoleBindingLookup
) -> int | None:
    if token is None:
        return None
    if token in seen:
        msg = "RoleBinding lookup repeated a continuation token"
        raise ApplierValidationError(
            msg,
            category="pagination",
            identities=(lookup.binding.resource_identity(scope=lookup.context.scope),),
        )
    seen.add(token)
    return token


def _append_matching_rolebindings(
    binding: RoleBinding,
    candidates: list[RoleBinding],
    matches: list[RoleBinding],
    *,
    resolved_role_guids: dict[str, str | None],
) -> None:
    for candidate in candidates:
        role_name = candidate.spec.role_ref.name
        role_guid = (
            resolved_role_guids.get(role_name) if role_name is not None else None
        )
        if _matches(binding, candidate, resolved_role_guid=role_guid):
            matches.append(candidate)


def _finish_rolebinding_lookup(
    binding: RoleBinding, matches: list[RoleBinding]
) -> RoleBinding | None:
    if len(matches) > 1:
        raise _ambiguous(binding)
    return matches[0] if matches else None


def _cache_missing_role_guids(
    candidates: list[RoleBinding],
    lookup: _RoleBindingLookup,
    resolved: dict[str, str | None],
) -> None:
    if lookup.binding.spec.role_ref.guid is None:
        return
    for candidate in candidates:
        role_name = candidate.spec.role_ref.name
        if (
            candidate.spec.role_ref.guid is None
            and role_name is not None
            and role_name not in resolved
        ):
            resolved[role_name] = _role_guid_for_name(
                lookup.client, role_name, lookup.context
            )


async def _cache_missing_role_guids_async(
    candidates: list[RoleBinding],
    lookup: _RoleBindingLookup,
    resolved: dict[str, str | None],
) -> None:
    if lookup.binding.spec.role_ref.guid is None:
        return
    for candidate in candidates:
        role_name = candidate.spec.role_ref.name
        if (
            candidate.spec.role_ref.guid is None
            and role_name is not None
            and role_name not in resolved
        ):
            resolved[role_name] = await _role_guid_for_name_async(
                lookup.client, role_name, lookup.context
            )


def _resolve_rolebinding_by_guid(lookup: _RoleBindingLookup) -> RoleBinding | None:
    try:
        found = lookup.client.get_role_binding(
            lookup.binding.metadata.guid,
            **organization_options(lookup.context),
        )
    except HttpNotFoundError:
        return None
    return _verify_rolebinding_guid(lookup, found)


async def _resolve_rolebinding_by_guid_async(
    lookup: _RoleBindingLookup,
) -> RoleBinding | None:
    try:
        found = await lookup.client.get_role_binding(
            lookup.binding.metadata.guid,
            **organization_options(lookup.context),
        )
    except HttpNotFoundError:
        return None
    return await _verify_rolebinding_guid_async(lookup, found)


def _list_rolebindings(lookup: _RoleBindingLookup) -> RoleBinding | None:
    matches: list[RoleBinding] = []
    resolved: dict[str, str | None] = {}
    continuation = 0
    seen: set[int] = set()
    while True:
        page = lookup.client.list_role_bindings(
            cont=continuation,
            limit=50,
            **_lookup_filters(lookup.binding),
            **organization_options(lookup.context),
        )
        candidates = page.items or []
        _cache_missing_role_guids(candidates, lookup, resolved)
        _append_matching_rolebindings(
            lookup.binding, candidates, matches, resolved_role_guids=resolved
        )
        metadata = page.metadata
        token = metadata.continue_ if metadata is not None else None
        next_token = _next_continuation(token, seen, lookup)
        if next_token is None:
            break
        continuation = next_token
    return _finish_rolebinding_lookup(lookup.binding, matches)


async def _list_rolebindings_async(
    lookup: _RoleBindingLookup,
) -> RoleBinding | None:
    matches: list[RoleBinding] = []
    resolved: dict[str, str | None] = {}
    continuation = 0
    seen: set[int] = set()
    while True:
        page = await lookup.client.list_role_bindings(
            cont=continuation,
            limit=50,
            **_lookup_filters(lookup.binding),
            **organization_options(lookup.context),
        )
        candidates = page.items or []
        await _cache_missing_role_guids_async(candidates, lookup, resolved)
        _append_matching_rolebindings(
            lookup.binding, candidates, matches, resolved_role_guids=resolved
        )
        metadata = page.metadata
        token = metadata.continue_ if metadata is not None else None
        next_token = _next_continuation(token, seen, lookup)
        if next_token is None:
            break
        continuation = next_token
    return _finish_rolebinding_lookup(lookup.binding, matches)


def resolve_rolebinding(
    client: Client, binding: RoleBinding, *, context: ResourceContext
) -> RoleBinding | None:
    """Resolve exactly one existing grant, honoring every supplied selector."""
    lookup = _RoleBindingLookup(binding=binding, context=context, client=client)
    if binding.metadata.guid is not None:
        return _resolve_rolebinding_by_guid(lookup)
    return _list_rolebindings(lookup)


async def resolve_rolebinding_async(
    client: AsyncClient, binding: RoleBinding, *, context: ResourceContext
) -> RoleBinding | None:
    """Resolve a grant through native async list/detail calls."""
    lookup = _RoleBindingLookup(binding=binding, context=context, client=client)
    if binding.metadata.guid is not None:
        return await _resolve_rolebinding_by_guid_async(lookup)
    return await _list_rolebindings_async(lookup)


def apply_rolebinding(
    client: Client, binding: RoleBinding, *, context: ResourceContext
) -> ResourceOutcome:
    """Report an exact existing grant or create exactly the requested grant."""
    context = _context_with_journal(context)
    identity, context = _effective_context(binding, context)
    existing = resolve_rolebinding(client, binding, context=context)
    if existing is None:
        payload = binding.model_copy(deep=True)
        update = BulkRoleBindingUpdate(new_bindings=[payload], old_bindings=[])
        record_write(
            context,
            "created",
            lambda: client.update_role_binding(update, **organization_options(context)),
        )
        status = "created"
    else:
        status = "exists"
    return _apply_outcome(identity, status, context)


async def apply_rolebinding_async(
    client: AsyncClient, binding: RoleBinding, *, context: ResourceContext
) -> ResourceOutcome:
    """Async exact grant existence check and creation."""
    context = _context_with_journal(context)
    identity, context = _effective_context(binding, context)
    existing = await resolve_rolebinding_async(client, binding, context=context)
    if existing is None:
        payload = binding.model_copy(deep=True)
        update = BulkRoleBindingUpdate(new_bindings=[payload], old_bindings=[])
        await record_write_async(
            context,
            "created",
            lambda: client.update_role_binding(update, **organization_options(context)),
        )
        status = "created"
    else:
        status = "exists"
    return _apply_outcome(identity, status, context)


def delete_rolebinding(
    client: Client, binding: RoleBinding, *, context: ResourceContext
) -> None:
    """Revoke only the exact resolved grant, with no replacement grant."""
    existing = resolve_rolebinding(client, binding, context=context)
    if existing is None:
        msg = "RoleBinding grant was not found"
        raise HttpNotFoundError(msg)
    update = BulkRoleBindingUpdate(old_bindings=[existing], new_bindings=[])
    record_write(
        context,
        "revoked",
        lambda: client.update_role_binding(update, **organization_options(context)),
    )


async def delete_rolebinding_async(
    client: AsyncClient, binding: RoleBinding, *, context: ResourceContext
) -> None:
    """Revoke an exact grant through native asynchronous SDK calls."""
    existing = await resolve_rolebinding_async(client, binding, context=context)
    if existing is None:
        msg = "RoleBinding grant was not found"
        raise HttpNotFoundError(msg)
    update = BulkRoleBindingUpdate(old_bindings=[existing], new_bindings=[])
    await record_write_async(
        context,
        "revoked",
        lambda: client.update_role_binding(update, **organization_options(context)),
    )


__all__ = [
    "apply_rolebinding",
    "apply_rolebinding_async",
    "delete_rolebinding",
    "delete_rolebinding_async",
    "resolve_rolebinding",
    "resolve_rolebinding_async",
]
