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

"""Collection facade ownership, offline planning, and dependency tests."""

import asyncio

import pytest

from rapyuta_io_sdk_v2.apply.applier import Applier, AsyncApplier
from rapyuta_io_sdk_v2.apply.errors import (
    ApplierUsageError,
    ApplierValidationError,
    MissingResourceContextError,
)
from rapyuta_io_sdk_v2.apply.source import ManifestSource
from rapyuta_io_sdk_v2.models.applier import ApplierOptions, ResourceScope
from rapyuta_io_sdk_v2.models.role import Role
from rapyuta_io_sdk_v2.models.rolebinding import (
    BulkRoleBindingUpdate,
    RoleBinding,
    RoleBindingList,
    RoleBindingSpec,
    RoleRef,
)
from rapyuta_io_sdk_v2.models.utils import BaseMetadata, Domain, ListMeta, Subject


def _role(name: str = "viewer") -> Role:
    return Role(metadata=BaseMetadata(name=name), spec={"rules": []})


def _binding() -> RoleBinding:
    return RoleBinding(
        metadata={},
        spec=RoleBindingSpec(
            roleRef=RoleRef(name="viewer"),
            domain=Domain(kind="Project", name="alpha"),
            subject=Subject(kind="User", name="ava"),
        ),
    )


def test_empty_and_dry_run_are_client_free_and_return_input_order() -> None:
    empty = Applier(ManifestSource())
    assert empty.apply().successful
    assert empty.delete().successful

    resources = [_role("first"), _role("second")]
    applier = Applier(ManifestSource(resources=resources))
    plan = applier.apply(dry_run=True)
    assert plan.dry_run is True
    assert [item.identity.name for item in plan.outcomes] == ["first", "second"]
    assert [item.planned_action for item in plan.outcomes] == [
        "create_or_update",
        "create_or_update",
    ]
    inspected = applier.inspect()
    inspected.resolved_manifests[0].metadata.name = "changed"
    assert applier.inspect().resolved_manifests[0].metadata.name == "first"


def test_live_apply_requires_exact_sync_client_and_keeps_it_open(
    configured_client: object,
) -> None:
    client = configured_client
    requests: list[str] = []

    def create_role(resource: Role, **kwargs: object) -> Role:
        requests.append("create")
        assert kwargs["organization_guid"] == "dummy-organization"
        return resource

    client.create_role = create_role
    applier = Applier(ManifestSource(resources=[_role()]))
    result = applier.apply(client)
    assert result.successful
    assert result.outcomes[0].completed_actions == ("created",)
    assert requests == ["create"]
    assert client.c.is_closed is False


def test_missing_wrong_mode_and_pinned_scope_fail_before_requests(
    configured_client: object,
) -> None:
    applier = Applier(ManifestSource(resources=[_role()]))
    with pytest.raises(MissingResourceContextError):
        applier.apply()
    with pytest.raises(ApplierUsageError, match="sync Applier requires"):
        applier.apply(object())

    conflict = Applier(
        ManifestSource(resources=[_role()]),
        ApplierOptions(scope=ResourceScope(organization_guid="another-org")),
    )
    with pytest.raises(ApplierValidationError, match="conflicts"):
        conflict.apply(configured_client)


@pytest.mark.asyncio
async def test_sync_facade_rejects_active_loop_before_platform_work(
    configured_client: object,
) -> None:
    applier = Applier(ManifestSource(resources=[_role()]))
    with pytest.raises(ApplierUsageError, match="active event loop"):
        applier.apply(configured_client)


def test_scheduler_applies_managed_prerequisites_before_binding(
    configured_client: object,
) -> None:
    client = configured_client
    events: list[str] = []

    def create_role(resource: Role, **_kwargs: object) -> Role:
        events.append("role")
        return resource

    def list_bindings(**_kwargs: object) -> RoleBindingList:
        events.append("lookup")
        return RoleBindingList(items=[], metadata=ListMeta())

    def update_binding(
        payload: BulkRoleBindingUpdate, **_kwargs: object
    ) -> BulkRoleBindingUpdate:
        events.append("grant")
        return payload

    client.create_role = create_role
    client.list_role_bindings = list_bindings
    client.update_role_binding = update_binding
    applier = Applier(ManifestSource(resources=[_binding(), _role()]))
    result = applier.apply(client)
    assert result.successful
    assert events == ["role", "lookup", "grant"]
    assert [item.identity.kind for item in result.outcomes] == [
        "rolebinding",
        "role",
    ]


@pytest.mark.asyncio
async def test_async_facade_requires_async_client_before_work() -> None:
    applier = AsyncApplier(ManifestSource(resources=[_role()]))
    with pytest.raises(MissingResourceContextError):
        await applier.apply()
    with pytest.raises(ApplierUsageError, match="AsyncApplier requires"):
        await applier.apply(object())


@pytest.mark.asyncio
async def test_async_facade_bounds_native_concurrent_writes(
    configured_async_client: object,
) -> None:
    client = configured_async_client
    active = 0
    maximum = 0

    async def create_role(resource: Role, **_kwargs: object) -> Role:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return resource

    client.create_role = create_role
    applier = AsyncApplier(
        ManifestSource(resources=[_role("a"), _role("b"), _role("c")]),
        ApplierOptions(workers=2),
    )
    result = await applier.apply(client)
    assert result.successful
    expected_maximum = 2
    expected_outcomes = 3
    assert maximum == expected_maximum
    assert len(result.outcomes) == expected_outcomes


@pytest.mark.asyncio
async def test_async_cancellation_publishes_settled_uncertain_write(
    configured_async_client: object,
) -> None:
    client = configured_async_client
    started = asyncio.Event()
    release = asyncio.Event()

    async def create_role(resource: Role, **_kwargs: object) -> Role:
        started.set()
        await release.wait()
        return resource

    client.create_role = create_role
    applier = AsyncApplier(ManifestSource(resources=[_role()]))
    operation = asyncio.create_task(applier.apply(client))
    await started.wait()
    operation.cancel()
    with pytest.raises(asyncio.CancelledError) as caught:
        await operation
    assert isinstance(caught.value, asyncio.CancelledError)
    assert applier.last_result is not None
    outcome = applier.last_result.outcomes[0]
    assert outcome.incomplete_reason == "cancelled"
    assert outcome.write_uncertain is True


def test_no_client_is_retained_between_calls(configured_client: object) -> None:
    client = configured_client
    client.create_role = lambda resource, **_kwargs: resource
    applier = Applier(ManifestSource(resources=[_role()]))
    applier.apply(client)
    assert not any(value is client for value in vars(applier).values())
