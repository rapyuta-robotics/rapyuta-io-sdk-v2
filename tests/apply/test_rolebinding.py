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

"""Exact grant matching tests for RoleBinding lifecycle helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from rapyuta_io_sdk_v2.apply._resources.rolebinding import (
    apply_rolebinding,
    apply_rolebinding_async,
    delete_rolebinding_async,
    resolve_rolebinding,
)
from rapyuta_io_sdk_v2.apply.errors import ApplierValidationError
from rapyuta_io_sdk_v2.models.applier import (
    ResourceContext,
    ResourceOutcome,
    ResourceScope,
)
from rapyuta_io_sdk_v2.models.progress import MutationJournal
from rapyuta_io_sdk_v2.models.rolebinding import (
    BulkRoleBindingUpdate,
    RoleBinding,
    RoleBindingList,
    RoleBindingMetadata,
    RoleBindingSpec,
    RoleRef,
)
from rapyuta_io_sdk_v2.models.utils import Domain, ListMeta, Subject

TWO_PAGES = 2


def _binding(
    *,
    role_name: str | None = "viewer",
    role_guid: str | None = None,
    guid: str | None = None,
) -> RoleBinding:
    return RoleBinding(
        metadata=RoleBindingMetadata(guid=guid),
        spec=RoleBindingSpec(
            roleRef=RoleRef(name=role_name, guid=role_guid),
            domain=Domain(kind="Project", name="alpha", guid="project-1"),
            subject=Subject(kind="User", name="ava", guid="user-1"),
        ),
    )


def _page(*items: RoleBinding, continuation: int | None = None) -> RoleBindingList:
    return RoleBindingList(items=list(items), metadata=ListMeta(continue_=continuation))


@pytest.mark.parametrize("missing_kind", ["subject", "domain"])
def test_identity_rejects_missing_subject_or_domain_kind_without_mutation(
    missing_kind: str,
) -> None:
    binding = RoleBinding(
        metadata={},
        spec=RoleBindingSpec(
            roleRef=RoleRef(name="viewer"),
            domain=Domain(
                name="alpha", kind=None if missing_kind == "domain" else "Project"
            ),
            subject=Subject(
                name="ava", kind=None if missing_kind == "subject" else "User"
            ),
        ),
    )
    before = binding.model_dump(exclude_unset=True, mode="python")

    with pytest.raises(ValueError, match=f"{missing_kind} kind is required"):
        binding.resource_identity()

    assert binding.model_dump(exclude_unset=True, mode="python") == before


def test_grant_creation_uses_one_typed_new_binding_and_reports_progress() -> None:
    requested = _binding()
    calls: list[BulkRoleBindingUpdate] = []

    def list_bindings(**kwargs: object) -> RoleBindingList:
        assert kwargs["role_names"] == ["viewer"]
        assert kwargs["subject_guids"] == ["user-1"]
        return _page()

    def update_bindings(
        payload: BulkRoleBindingUpdate, **_kwargs: object
    ) -> BulkRoleBindingUpdate:
        calls.append(payload)
        return payload

    client = SimpleNamespace(
        list_role_bindings=list_bindings,
        update_role_binding=update_bindings,
    )
    outcome = apply_rolebinding(
        client,
        requested,
        context=ResourceContext(scope=ResourceScope(organization_guid="org-1")),
    )

    assert outcome.status == "created"
    assert outcome.completed_actions == ("created",)
    assert calls[0].new_bindings == [requested]
    assert calls[0].old_bindings == []


def test_exact_match_checks_all_supplied_selectors_and_pagination() -> None:
    requested = _binding()
    wrong_subject = _binding().model_copy(
        update={
            "spec": _binding().spec.model_copy(
                update={"subject": Subject(kind="User", name="ava", guid="other")}
            )
        }
    )
    calls = 0

    def list_bindings(*, cont: int = 0, **_kwargs: object) -> RoleBindingList:
        nonlocal calls
        calls += 1
        if cont == 0:
            return _page(wrong_subject, continuation=4)
        return _page(requested)

    client = SimpleNamespace(list_role_bindings=list_bindings)
    assert (
        resolve_rolebinding(client, requested, context=ResourceContext()) == requested
    )
    assert calls == TWO_PAGES


def test_multiple_exact_matches_and_guid_tuple_mismatch_are_rejected() -> None:
    requested = _binding()
    client = SimpleNamespace(
        list_role_bindings=lambda **_kwargs: _page(
            requested, requested.model_copy(deep=True)
        )
    )
    with pytest.raises(ApplierValidationError, match="multiple exact"):
        resolve_rolebinding(client, requested, context=ResourceContext())

    by_guid = _binding(guid="binding-1")
    wrong = _binding(guid="binding-1").model_copy(
        update={
            "spec": _binding(guid="binding-1").spec.model_copy(
                update={"domain": Domain(kind="Project", name="other")}
            )
        }
    )
    detail_client = SimpleNamespace(get_role_binding=lambda *_args, **_kwargs: wrong)
    with pytest.raises(ApplierValidationError, match="different grant"):
        resolve_rolebinding(detail_client, by_guid, context=ResourceContext())


def test_guid_only_role_omits_role_name_filter_and_resolves_response_name() -> None:
    requested = _binding(role_name=None, role_guid="role-1")
    candidate = _binding()
    calls: list[dict[str, object]] = []

    def list_bindings(**kwargs: object) -> RoleBindingList:
        calls.append(dict(kwargs))
        return _page(candidate)

    role = SimpleNamespace(metadata=SimpleNamespace(guid="role-1"))
    client = SimpleNamespace(
        list_role_bindings=list_bindings,
        get_role=lambda *_args, **_kwargs: role,
    )
    assert (
        resolve_rolebinding(client, requested, context=ResourceContext()) == candidate
    )
    assert "role_names" not in calls[0]


@pytest.mark.asyncio
async def test_async_grant_and_revocation_send_only_the_exact_binding() -> None:
    requested = _binding()
    calls: list[BulkRoleBindingUpdate] = []
    lookup_calls = 0

    async def list_bindings(**_kwargs: object) -> RoleBindingList:
        nonlocal lookup_calls
        lookup_calls += 1
        return _page() if lookup_calls == 1 else _page(requested)

    async def update_bindings(
        payload: BulkRoleBindingUpdate, **_kwargs: object
    ) -> BulkRoleBindingUpdate:
        calls.append(payload)
        return payload

    client = SimpleNamespace(
        list_role_bindings=list_bindings,
        update_role_binding=update_bindings,
    )
    outcome = await apply_rolebinding_async(
        client, requested, context=ResourceContext()
    )
    await delete_rolebinding_async(client, requested, context=ResourceContext())

    assert outcome.status == "created"
    assert calls[0].new_bindings == [requested]
    assert calls[0].old_bindings == []
    assert calls[1].old_bindings == [requested]
    assert calls[1].new_bindings == []


async def _apply_direct_binding(
    binding: RoleBinding,
    client: object,
    *,
    context: ResourceContext,
    asynchronous: bool,
) -> ResourceOutcome:
    if asynchronous:
        return await binding.apply_async(client, context=context)
    return binding.apply(client, context=context)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("conflict", [False, True])
@pytest.mark.asyncio
async def test_direct_grant_reconciles_metadata_scope(
    *, asynchronous: bool, conflict: bool
) -> None:
    requested = _binding()
    requested.metadata.organization_guid = "org-a"
    before = requested.model_dump(exclude_unset=True)
    journal = MutationJournal()
    context = ResourceContext(
        scope=ResourceScope(organization_guid="org-b") if conflict else ResourceScope(),
        progress=journal,
    )
    lookup = (
        AsyncMock(return_value=_page()) if asynchronous else Mock(return_value=_page())
    )
    grant = AsyncMock() if asynchronous else Mock()
    client = SimpleNamespace(list_role_bindings=lookup, update_role_binding=grant)
    if conflict:
        with pytest.raises(ApplierValidationError, match="scope conflicts"):
            await _apply_direct_binding(
                requested, client, context=context, asynchronous=asynchronous
            )
        lookup.assert_not_called()
        grant.assert_not_called()
        assert journal.snapshot() == ()
    else:
        outcome = await _apply_direct_binding(
            requested, client, context=context, asynchronous=asynchronous
        )
        assert lookup.call_args.kwargs["organization_guid"] == "org-a"
        assert grant.call_args.kwargs["organization_guid"] == "org-a"
        assert outcome.identity.scope.organization_guid == "org-a"
        assert outcome.completed_actions == ("created",)
    assert requested.model_dump(exclude_unset=True) == before
    assert context.progress is journal
