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

"""Deterministic ready-cohort barriers and dependency scheduling tests."""

from __future__ import annotations

import asyncio

import pytest

from rapyuta_io_sdk_v2.apply.applier import Applier, AsyncApplier
from rapyuta_io_sdk_v2.apply.errors import ApplierExecutionError
from rapyuta_io_sdk_v2.apply.source import ManifestSource
from rapyuta_io_sdk_v2.models.applier import ApplierOptions
from rapyuta_io_sdk_v2.models.role import Role
from rapyuta_io_sdk_v2.models.rolebinding import (
    BulkRoleBindingUpdate,
    RoleBinding,
    RoleBindingList,
    RoleBindingSpec,
    RoleRef,
)
from rapyuta_io_sdk_v2.models.utils import BaseMetadata, Domain, ListMeta, Subject

WORKER_LIMIT = 2


def _role(name: str) -> Role:
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


@pytest.mark.asyncio
async def test_worker_bound_uses_event_barrier_and_preserves_input_order(
    configured_async_client: object,
) -> None:
    client = configured_async_client
    active = 0
    maximum = 0
    started: list[str] = []
    two_started = asyncio.Event()
    release = asyncio.Event()

    async def create_role(resource: Role, **_kwargs: object) -> Role:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        started.append(resource.metadata.name)
        if len(started) == WORKER_LIMIT:
            two_started.set()
        await release.wait()
        active -= 1
        return resource

    client.create_role = create_role
    applier = AsyncApplier(
        ManifestSource(resources=(_role("first"), _role("second"), _role("third"))),
        ApplierOptions(workers=WORKER_LIMIT),
    )
    operation = asyncio.create_task(applier.apply(client))
    await asyncio.wait_for(two_started.wait(), timeout=1)
    assert len(started) == WORKER_LIMIT
    assert maximum == WORKER_LIMIT
    release.set()

    result = await operation
    assert result.successful
    assert [item.identity.name for item in result.outcomes] == [
        "first",
        "second",
        "third",
    ]
    assert maximum == WORKER_LIMIT


@pytest.mark.asyncio
async def test_failed_prerequisite_blocks_managed_role_binding(
    configured_async_client: object,
) -> None:
    client = configured_async_client
    events: list[str] = []

    async def create_role(_resource: Role, **_kwargs: object) -> Role:
        events.append("role")
        raise RuntimeError

    async def list_bindings(**_kwargs: object) -> RoleBindingList:
        events.append("lookup")
        return RoleBindingList(items=[], metadata=ListMeta())

    async def update_binding(
        payload: BulkRoleBindingUpdate, **_kwargs: object
    ) -> BulkRoleBindingUpdate:
        events.append("grant")
        return payload

    client.create_role = create_role
    client.list_role_bindings = list_bindings
    client.update_role_binding = update_binding
    applier = AsyncApplier(
        ManifestSource(resources=(_binding(), _role("viewer"))),
        ApplierOptions(workers=2),
    )

    with pytest.raises(ApplierExecutionError) as caught:
        await applier.apply(client)

    assert events == ["role"]
    assert caught.value.result.outcomes[0].status == "not_completed"
    assert caught.value.result.outcomes[1].status == "failed"


@pytest.mark.asyncio
async def test_resource_failure_cancels_chunk_sibling_and_settles_before_return(
    configured_async_client: object,
) -> None:
    client = configured_async_client
    blocked_started = asyncio.Event()
    blocked_cancelled = asyncio.Event()
    calls: list[str] = []

    async def create_role(resource: Role, **_kwargs: object) -> Role:
        name = resource.metadata.name
        calls.append(name)
        if name == "blocked":
            blocked_started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                blocked_cancelled.set()
                raise
        if name == "failure":
            await blocked_started.wait()
            raise RuntimeError
        return resource

    client.create_role = create_role
    applier = AsyncApplier(
        ManifestSource(resources=(_role("failure"), _role("blocked"), _role("queued"))),
        ApplierOptions(workers=WORKER_LIMIT),
    )

    with pytest.raises(ApplierExecutionError) as caught:
        await asyncio.wait_for(applier.apply(client), timeout=1)

    assert blocked_cancelled.is_set()
    assert calls == ["failure", "blocked"]
    outcomes = caught.value.result.outcomes
    assert [item.status for item in outcomes] == [
        "failed",
        "not_completed",
        "not_completed",
    ]
    assert outcomes[1].incomplete_reason == "cancelled"
    assert outcomes[2].incomplete_reason == "not_started"
    assert [item.write_uncertain for item in outcomes] == [True, True, False]
    assert applier.last_result == caught.value.result


def test_delete_reverses_managed_role_binding_edge(
    configured_client: object,
) -> None:
    client = configured_client
    events: list[str] = []
    binding = _binding()

    def list_bindings(**_kwargs: object) -> RoleBindingList:
        events.append("lookup")
        return RoleBindingList(items=[binding], metadata=ListMeta())

    def revoke(
        payload: BulkRoleBindingUpdate, **_kwargs: object
    ) -> BulkRoleBindingUpdate:
        events.append("revoke")
        return payload

    def delete_role(_name: str, **_kwargs: object) -> None:
        events.append("role")

    client.list_role_bindings = list_bindings
    client.update_role_binding = revoke
    client.delete_role = delete_role
    result = Applier(ManifestSource(resources=(_role("viewer"), binding))).delete(
        client
    )

    assert result.successful
    assert events == ["lookup", "revoke", "role"]
