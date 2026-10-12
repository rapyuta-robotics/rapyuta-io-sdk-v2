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

"""Synchronous lifecycle policies and mutation outcomes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rapyuta_io_sdk_v2.apply.applier import Applier, AsyncApplier
from rapyuta_io_sdk_v2.apply.errors import ApplierExecutionError, ApplierValidationError
from rapyuta_io_sdk_v2.apply.source import ManifestSource
from rapyuta_io_sdk_v2.exceptions import (
    HttpAlreadyExistsError,
    UnauthorizedAccessError,
)
from rapyuta_io_sdk_v2.models.organization import Organization
from rapyuta_io_sdk_v2.models.role import Role
from rapyuta_io_sdk_v2.models.usergroup import UserGroup, UserGroupList, UserGroupSpec
from rapyuta_io_sdk_v2.models.utils import BaseMetadata, ListMeta

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.models.package import Package


def _role() -> Role:
    return Role(metadata=BaseMetadata(name="viewer"), spec={"rules": []})


def test_conflict_and_creation_denial_fall_back_to_role_update(
    configured_client: object,
) -> None:
    client = configured_client
    attempts: list[str] = []

    def create_role(_resource: Role, **_kwargs: object) -> Role:
        attempts.append("create")
        raise HttpAlreadyExistsError

    def update_role(resource: Role, **_kwargs: object) -> Role:
        attempts.append("update")
        return resource

    client.create_role = create_role
    client.update_role = update_role
    result = Applier(ManifestSource(resources=(_role(),))).apply(client)

    assert attempts == ["create", "update"]
    assert result.outcomes[0].status == "updated"
    assert result.outcomes[0].completed_actions == ("updated",)

    attempts.clear()

    def denied_create(_resource: Role, **_kwargs: object) -> Role:
        attempts.append("create")
        raise UnauthorizedAccessError

    client.create_role = denied_create
    result = Applier(ManifestSource(resources=(_role(),))).apply(client)
    assert attempts == ["create", "update"]
    assert result.outcomes[0].completed_actions == ("updated",)


def test_organization_apply_updates_guid_without_attempting_create(
    configured_client: object,
) -> None:
    client = configured_client
    calls: list[tuple[str, str]] = []
    organization = Organization(
        metadata=BaseMetadata(name="org", guid="target-org"),
        spec={"members": []},
    )

    def update_organization(
        resource: Organization, guid: str, **_kwargs: object
    ) -> Organization:
        calls.append((resource.metadata.name, guid))
        return resource

    client.update_organization = update_organization
    client.create_organization = lambda *_args, **_kwargs: pytest.fail(
        "update-only Organization attempted create"
    )
    result = Applier(ManifestSource(resources=(organization,))).apply(client)

    assert calls == [("org", "target-org")]
    assert result.outcomes[0].status == "updated"
    assert result.outcomes[0].completed_actions == ("updated",)


def test_denied_create_for_immutable_package_is_not_reported_as_exists(
    configured_client: object,
    resource_fixtures: dict[str, object],
) -> None:
    client = configured_client
    package = resource_fixtures["package"]
    update_calls: list[str] = []

    def denied_create(_resource: Package, **_kwargs: object) -> Package:
        raise UnauthorizedAccessError

    def update_package(_resource: Package, **_kwargs: object) -> Package:
        update_calls.append("update")
        return package

    client.create_package = denied_create
    client.update_package = update_package
    applier = Applier(ManifestSource(resources=(package,)))

    with pytest.raises(ApplierExecutionError) as caught:
        applier.apply(client)

    assert update_calls == []
    assert caught.value.result.outcomes[0].status == "failed"
    assert caught.value.result.outcomes[0].completed_actions == ()


def test_organization_without_guid_fails_preflight_before_any_write(
    configured_client: object,
) -> None:
    client = configured_client
    role_writes: list[str] = []
    client.create_role = lambda *_args, **_kwargs: role_writes.append("role")
    applier = Applier(
        ManifestSource(
            resources=(
                _role(),
                Organization(metadata=BaseMetadata(name="org"), spec={"members": []}),
            )
        )
    )

    with pytest.raises(ApplierValidationError, match=r"metadata\.guid"):
        applier.apply(client)

    assert role_writes == []


def _usergroup() -> UserGroup:
    return UserGroup(metadata=BaseMetadata(name="operators"), spec=UserGroupSpec())


def _existing_usergroup() -> UserGroup:
    return UserGroup(
        metadata=BaseMetadata(
            name="operators",
            guid="operators-guid",
            organization_guid="dummy-organization",
        ),
        spec=UserGroupSpec(),
    )


def test_reapplying_name_only_usergroup_resolves_guid_before_sync_update(
    configured_client: object,
) -> None:
    client = configured_client
    source_group = _usergroup()
    existing = _existing_usergroup()
    create_calls = 0
    update_guids: list[str | None] = []

    def create(_payload: UserGroup, **_kwargs: object) -> UserGroup:
        nonlocal create_calls
        create_calls += 1
        if create_calls > 1:
            raise HttpAlreadyExistsError
        return existing

    def list_groups(**_kwargs: object) -> UserGroupList:
        return UserGroupList(items=[existing], metadata=ListMeta())

    def update(payload: UserGroup, **_kwargs: object) -> UserGroup:
        update_guids.append(payload.metadata.guid)
        return payload

    client.create_user_group = create
    client.list_user_groups = list_groups
    client.update_user_group = update
    applier = Applier(ManifestSource(resources=(source_group,)))

    first = applier.apply(client)
    second = applier.apply(client)

    assert first.outcomes[0].status == "created"
    assert second.outcomes[0].status == "updated"
    assert update_guids == ["operators-guid"]
    assert source_group.metadata.guid is None


@pytest.mark.asyncio
async def test_reapplying_name_only_usergroup_resolves_guid_before_async_update(
    configured_async_client: object,
) -> None:
    client = configured_async_client
    source_group = _usergroup()
    existing = _existing_usergroup()
    create_calls = 0
    update_guids: list[str | None] = []

    async def create(_payload: UserGroup, **_kwargs: object) -> UserGroup:
        nonlocal create_calls
        create_calls += 1
        if create_calls > 1:
            raise HttpAlreadyExistsError
        return existing

    async def list_groups(**_kwargs: object) -> UserGroupList:
        return UserGroupList(items=[existing], metadata=ListMeta())

    async def update(payload: UserGroup, **_kwargs: object) -> UserGroup:
        update_guids.append(payload.metadata.guid)
        return payload

    client.create_user_group = create
    client.list_user_groups = list_groups
    client.update_user_group = update
    applier = AsyncApplier(ManifestSource(resources=(source_group,)))

    first = await applier.apply(client)
    second = await applier.apply(client)

    assert first.outcomes[0].status == "created"
    assert second.outcomes[0].status == "updated"
    assert update_guids == ["operators-guid"]
    assert source_group.metadata.guid is None
