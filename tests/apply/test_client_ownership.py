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

"""Per-call client ownership and sequential facade reuse tests."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from rapyuta_io_sdk_v2.apply.applier import Applier, AsyncApplier
from rapyuta_io_sdk_v2.apply.errors import ApplierUsageError
from rapyuta_io_sdk_v2.apply.source import ManifestSource
from rapyuta_io_sdk_v2.client import Client
from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.models.role import Role
from rapyuta_io_sdk_v2.models.utils import BaseMetadata

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient


def _role() -> Role:
    return Role(metadata=BaseMetadata(name="reader"), spec={"rules": []})


def test_one_sync_facade_reuses_exact_clients_and_scopes_sequentially(
    configured_client: Client,
) -> None:
    first = configured_client
    second = Client(
        Configuration(
            auth_token="second-token",
            organization_guid="second-org",
            project_guid="second-project",
            environment="local",
        )
    )
    organizations: list[str] = []

    def create_role(resource: Role, **kwargs: object) -> Role:
        organizations.append(str(kwargs["organization_guid"]))
        return resource

    first.create_role = create_role
    second.create_role = create_role
    applier = Applier(ManifestSource(resources=(_role(),)))
    try:
        assert applier.apply(first).successful
        assert applier.apply(second).successful
        assert organizations == ["dummy-organization", "second-org"]
        assert first.c.is_closed is False
        assert second.c.is_closed is False
        assert all(
            value is not first and value is not second
            for value in vars(applier).values()
        )
    finally:
        second.c.close()


@pytest.mark.asyncio
async def test_async_facade_uses_and_leaves_supplied_async_client_open(
    configured_async_client: AsyncClient,
) -> None:
    client = configured_async_client
    received: list[AsyncClient] = []

    async def create_role(resource: Role, **_kwargs: object) -> Role:
        received.append(client)
        return resource

    client.create_role = create_role
    applier = AsyncApplier(ManifestSource(resources=(_role(),)))

    assert (await applier.apply(client)).successful
    assert received == [client]
    assert client.c.is_closed is False
    assert not any(value is client for value in vars(applier).values())


@pytest.mark.asyncio
async def test_concurrent_call_on_one_facade_fails_without_stopping_active_call(
    configured_async_client: AsyncClient,
) -> None:
    client = configured_async_client
    started = asyncio.Event()
    release = asyncio.Event()

    async def create_role(resource: Role, **_kwargs: object) -> Role:
        started.set()
        await release.wait()
        return resource

    client.create_role = create_role
    applier = AsyncApplier(ManifestSource(resources=(_role(),)))
    active = asyncio.create_task(applier.apply(client))
    await started.wait()
    with pytest.raises(ApplierUsageError, match="active operation"):
        await applier.apply(client)
    release.set()

    assert (await active).successful
