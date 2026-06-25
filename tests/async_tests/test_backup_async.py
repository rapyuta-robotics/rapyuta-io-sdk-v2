import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import Backup, BackupList
from tests.data import (
    backup_body,
    backup_model_mock,
    backuplist_model_mock,
)
from tests.utils.fixtures import async_client


@pytest.mark.asyncio
async def test_list_backups_success(
    async_client, backuplist_model_mock, mocker: MockFixture
):
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
    async_client, backup_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=backup_model_mock,
    )

    response = await async_client.get_backup(guid="backup-mockbackup12345678901")

    assert isinstance(response, Backup)
    assert response.spec.schedule == "0 2 * * *"
    assert response.status.latest_run.verification.check == "Passed"


@pytest.mark.asyncio
async def test_get_backup_not_found(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "backup not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.get_backup(guid="notfound")

    assert str(exc.value) == "backup not found"


@pytest.mark.asyncio
async def test_create_backup_success(
    async_client, backup_body, backup_model_mock, mocker: MockFixture
):
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
    async_client, backup_body, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.create_backup(body=backup_body)

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_delete_backup_success(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    response = await async_client.delete_backup(guid="backup-mockbackup12345678901")

    assert response is None
