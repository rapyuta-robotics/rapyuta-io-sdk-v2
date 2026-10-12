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

"""Client-free inspection and lifecycle preview contract tests."""

from __future__ import annotations

import asyncio
import json
import subprocess
from typing import TYPE_CHECKING

import pytest

from rapyuta_io_sdk_v2.apply.applier import Applier, AsyncApplier
from rapyuta_io_sdk_v2.apply.errors import (
    ApplierUsageError,
    ApplierValidationError,
    UnsupportedResourceOperationError,
)
from rapyuta_io_sdk_v2.apply.source import ManifestSource
from rapyuta_io_sdk_v2.models.organization import Organization, OrganizationSpec
from rapyuta_io_sdk_v2.models.role import Role
from rapyuta_io_sdk_v2.models.secret import DockerSpec, Secret, SecretSpec
from rapyuta_io_sdk_v2.models.usergroup import UserGroup, UserGroupSpec
from rapyuta_io_sdk_v2.models.utils import BaseMetadata

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client

RESOURCE_COUNT = 2


def _role(name: str) -> Role:
    return Role(metadata=BaseMetadata(name=name), spec={"rules": []})


def _response_secret() -> Secret:
    return Secret(
        metadata=BaseMetadata(name="registry"),
        spec=SecretSpec(
            type="Docker",
            docker=DockerSpec(username="builder", email="builder@example.test"),
            secret_keys=[".dockerconfigjson"],
        ),
    )


def _response_group() -> UserGroup:
    return UserGroup(
        metadata=BaseMetadata(name="operators", guid="group-guid"),
        spec=UserGroupSpec(members_count=2),
    )


def _organization(*, retain: bool = False) -> Organization:
    metadata = BaseMetadata(name="org", guid="org-guid")
    if retain:
        metadata.labels = {"rapyuta.io/deletionPolicy": "retain"}
    return Organization(metadata=metadata, spec=OrganizationSpec(members=[]))


def _organization_without_guid() -> Organization:
    return Organization(
        metadata=BaseMetadata(name="org"), spec=OrganizationSpec(members=[])
    )


def test_sync_inspection_and_previews_are_independent_and_client_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        message = "preview unexpectedly invoked SOPS"
        raise AssertionError(message)

    monkeypatch.setattr(subprocess, "run", unexpected)
    applier = Applier(ManifestSource(resources=(_role("first"), _role("second"))))

    inspection = applier.inspect()
    inspection.resolved_manifests[0].metadata.name = "changed"
    apply_plan = applier.apply(dry_run=True)
    delete_plan = applier.delete(dry_run=True)

    assert [item.identity.name for item in apply_plan.outcomes] == [
        "first",
        "second",
    ]
    assert [item.planned_action for item in apply_plan.outcomes] == [
        "create_or_update",
        "create_or_update",
    ]
    assert [item.planned_action for item in delete_plan.outcomes] == [
        "delete",
        "delete",
    ]
    assert applier.inspect().resolved_manifests[0].metadata.name == "first"
    assert applier.last_result == delete_plan


@pytest.mark.asyncio
async def test_async_preview_and_inspect_need_no_client_or_sops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected(*_args: object, **_kwargs: object) -> None:
        message = "preview unexpectedly spawned SOPS"
        raise AssertionError(message)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", unexpected)
    applier = AsyncApplier(ManifestSource(resources=(_role("async-role"),)))

    assert len(applier.inspect().resolved_manifests) == 1
    apply_plan = await applier.apply(dry_run=True)
    delete_plan = await applier.delete(dry_run=True)

    assert apply_plan.outcomes[0].planned_action == "create_or_update"
    assert delete_plan.outcomes[0].planned_action == "delete"
    assert applier.last_result == delete_plan


def test_organization_prepares_and_inspects_but_delete_is_operation_preflight() -> None:
    retained = Applier(ManifestSource(resources=(_organization(retain=True),)))
    assert len(retained.inspect().resolved_manifests) == 1
    assert retained.delete(dry_run=True).outcomes[0].status == "retained"

    unsupported = Applier(ManifestSource(resources=(_organization(),)))
    assert len(unsupported.inspect().resource_identities) == 1
    with pytest.raises(UnsupportedResourceOperationError):
        unsupported.delete(dry_run=True)


def test_organization_without_guid_fails_apply_preview_preflight() -> None:
    applier = Applier(ManifestSource(resources=(_organization_without_guid(),)))

    with pytest.raises(ApplierValidationError, match=r"metadata\.guid"):
        applier.apply(dry_run=True)

    async_applier = AsyncApplier(
        ManifestSource(resources=(_organization_without_guid(),))
    )
    with pytest.raises(ApplierValidationError, match=r"metadata\.guid"):
        asyncio.run(async_applier.apply(dry_run=True))


def test_response_only_resources_prepare_and_delete_preview_without_create_fields() -> (
    None
):
    source = ManifestSource(resources=(_response_secret(), _response_group()))
    applier = Applier(source)

    assert [item.kind for item in applier.inspect().resource_identities] == [
        "secret",
        "usergroup",
    ]
    delete_plan = applier.delete(dry_run=True)
    assert [item.planned_action for item in delete_plan.outcomes] == [
        "delete",
        "delete",
    ]
    with pytest.raises(ApplierValidationError, match="creation payload"):
        applier.apply(dry_run=True)


@pytest.mark.asyncio
async def test_async_response_only_resources_inspect_and_preview_delete() -> None:
    applier = AsyncApplier(
        ManifestSource(resources=(_response_secret(), _response_group()))
    )

    assert len(applier.inspect().resource_identities) == RESOURCE_COUNT
    result = await applier.delete(dry_run=True)
    assert [item.status for item in result.outcomes] == ["planned", "planned"]


@pytest.mark.parametrize("facade", [Applier, AsyncApplier])
def test_inspection_serializes_concrete_manifests(facade: type) -> None:
    secret = _response_secret()
    applier = facade(ManifestSource(resources=(_role("viewer"), secret)))
    inspection = applier.inspect()

    expected = tuple(item.model_dump() for item in inspection.resolved_manifests)
    assert inspection.model_dump()["resolved_manifests"] == expected
    assert json.loads(inspection.model_dump_json())["resolved_manifests"] == [
        item.model_dump(mode="json") for item in inspection.resolved_manifests
    ]
    assert inspection.model_dump(by_alias=True, exclude_unset=True)[
        "resolved_manifests"
    ] == tuple(
        item.model_dump(by_alias=True, exclude_unset=True)
        for item in inspection.resolved_manifests
    )


@pytest.mark.parametrize("operation", ["apply", "delete"])
def test_sync_preview_rejects_overlap_and_preserves_last_result(
    configured_client: Client, operation: str
) -> None:
    applier = Applier(ManifestSource(resources=(_role("viewer"),)))
    previous = applier.apply(dry_run=True)

    def create_role(payload: Role, **_kwargs: object) -> Role:
        with pytest.raises(ApplierUsageError, match="active operation"):
            getattr(applier, operation)(dry_run=True)
        assert applier.last_result is previous
        return payload

    configured_client.create_role = create_role
    result = applier.apply(configured_client)
    assert result.successful
    assert applier.last_result is result
    assert getattr(applier, operation)(dry_run=True).dry_run


@pytest.mark.parametrize("operation", ["apply", "delete"])
@pytest.mark.asyncio
async def test_async_preview_rejects_overlap_and_preserves_last_result(
    configured_async_client: AsyncClient, operation: str
) -> None:
    started, release = asyncio.Event(), asyncio.Event()
    applier = AsyncApplier(ManifestSource(resources=(_role("viewer"),)))
    previous = await applier.apply(dry_run=True)

    async def create_role(payload: Role, **_kwargs: object) -> Role:
        started.set()
        await release.wait()
        return payload

    configured_async_client.create_role = create_role
    active = asyncio.create_task(applier.apply(configured_async_client))
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        with pytest.raises(ApplierUsageError, match="active operation"):
            await getattr(applier, operation)(dry_run=True)
        assert applier.last_result is previous
    finally:
        release.set()
        result = await active
    assert result.successful
    assert applier.last_result is result
    assert (await getattr(applier, operation)(dry_run=True)).dry_run


@pytest.mark.parametrize("facade", [Applier, AsyncApplier])
def test_preview_failure_releases_operation_guard(facade: type) -> None:
    applier = facade(ManifestSource(resources=(_organization(),)))
    with pytest.raises(UnsupportedResourceOperationError):
        (
            applier.delete(dry_run=True)
            if facade is Applier
            else asyncio.run(applier.delete(dry_run=True))
        )

    result = (
        applier.apply(dry_run=True)
        if facade is Applier
        else asyncio.run(applier.apply(dry_run=True))
    )
    assert result.successful
    assert applier.last_result is result
