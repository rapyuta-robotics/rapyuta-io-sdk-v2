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

from rapyuta_io_sdk_v2.models import Backup, BackupList


@pytest.mark.asyncio
async def test_list_backups_success(
    *,
    async_client: AsyncClient,
    backuplist_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=backuplist_model_mock,
    )

    response = await async_client.list_backups(database="orders-db")

    assert isinstance(response, BackupList)
    assert len(response.items) == 1
    backup = response.items[0]
    assert backup.metadata.guid == "backup-mockbackup12345678901"
    assert backup.spec.database == "orders-db"
    assert backup.status.phase == "Ready"


@pytest.mark.asyncio
async def test_get_backup_success(
    *, async_client: AsyncClient, backup_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=backup_model_mock,
    )

    response = await async_client.get_backup(name="backup-mockbackup12345678901")

    assert isinstance(response, Backup)
    assert response.spec.schedule == "0 2 * * *"
    assert response.status.latest_run.verification.check == "Passed"


@pytest.mark.asyncio
async def test_get_backup_not_found(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "backup not found"},
    )

    with pytest.raises(Exception, match=r".+") as exc:
        await async_client.get_backup(name="notfound")

    assert str(exc.value) == "backup not found"


@pytest.mark.asyncio
async def test_create_backup_success(
    *,
    async_client: AsyncClient,
    backup_body: dict[str, Any],
    backup_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=202,
        json=backup_model_mock,
    )

    response = await async_client.create_backup(body=backup_body)

    assert isinstance(response, Backup)
    assert response.metadata.name == "orders-nightly"


@pytest.mark.asyncio
async def test_create_backup_unauthorized(
    *, async_client: AsyncClient, backup_body: dict[str, Any], mocker: MockFixture
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception, match=r".+") as exc:
        await async_client.create_backup(body=backup_body)

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_delete_backup_success(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    response = await async_client.delete_backup(name="backup-mockbackup12345678901")

    assert response is None
