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


from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import AsyncClient

from rapyuta_io_sdk_v2.models import Restore, RestoreList


@pytest.mark.asyncio
async def test_list_restores_success(
    *,
    async_client: AsyncClient,
    restorelist_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=restorelist_model_mock,
    )

    response = await async_client.list_restores(database="orders-db")

    assert isinstance(response, RestoreList)
    assert len(response.items) == 1
    assert response.items[0].status.restored_databases == ["orders"]
    # Restore is a sub-resource: the target database is in the route.
    assert "/v2/databases/orders-db/restores/" in mock_get.call_args.kwargs["url"]


@pytest.mark.asyncio
async def test_get_restore_success(
    *,
    async_client: AsyncClient,
    restore_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=restore_model_mock,
    )

    response = await async_client.get_restore(
        database="orders-db", name="orders-db-restore"
    )

    assert isinstance(response, Restore)
    assert response.spec.source.type == "backup"
    # Signed download links never reach a user-facing read.
    assert response.spec.source.archives[0].url is None


@pytest.mark.asyncio
async def test_get_restore_not_found(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "restore not found"},
    )

    with pytest.raises(Exception, match=r".+") as exc:
        await async_client.get_restore(database="orders-db", name="notfound")

    assert str(exc.value) == "restore not found"


@pytest.mark.asyncio
async def test_create_restore_success(
    *,
    async_client: AsyncClient,
    restore_body: dict[str, Any],
    restore_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=202,
        json=restore_model_mock,
    )

    response = await async_client.create_restore(
        body=Restore.model_validate(restore_body)
    )

    assert isinstance(response, Restore)
    assert "/v2/databases/orders-db/restores/" in mock_post.call_args.kwargs["url"]


@pytest.mark.asyncio
async def test_create_restore_migration_source(
    *,
    async_client: AsyncClient,
    restore_migration_body: dict[str, Any],
    restore_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=202,
        json=restore_model_mock,
    )

    await async_client.create_restore(
        body=Restore.model_validate(restore_migration_body)
    )

    sent = mock_post.call_args.kwargs["json"]
    assert sent["spec"]["source"]["type"] == "dataDirectory"
    assert sent["spec"]["source"]["sourceVersion"] == "17"


@pytest.mark.asyncio
async def test_create_restore_requires_target_database(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mocker.patch("httpx.AsyncClient.post")

    body = {
        "metadata": {"name": "orphan-restore"},
        "spec": {"source": {"type": "backup", "backupName": "orders-nightly"}},
    }

    with pytest.raises(ValueError, match="target database is not specified"):
        await async_client.create_restore(body=Restore.model_validate(body))


@pytest.mark.asyncio
async def test_create_restore_conflict(
    *, async_client: AsyncClient, restore_body: dict[str, Any], mocker: MockFixture
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "a restore is already in progress for this database"},
    )

    # Two concurrent pg_restores into one live cluster is data loss, so the
    # apiserver refuses the second.
    with pytest.raises(Exception, match=r".+") as exc:
        await async_client.create_restore(body=Restore.model_validate(restore_body))

    assert "already in progress" in str(exc.value)
