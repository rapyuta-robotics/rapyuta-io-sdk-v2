import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import Restore, RestoreList
from tests.data import (
    restore_body,
    restore_migration_body,
    restore_model_mock,
    restorelist_model_mock,
)
from tests.utils.fixtures import async_client


@pytest.mark.asyncio
async def test_list_restores_success(
    async_client, restorelist_model_mock, mocker: MockFixture
):
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
async def test_get_restore_success(async_client, restore_model_mock, mocker: MockFixture):
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
async def test_get_restore_not_found(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "restore not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.get_restore(database="orders-db", name="notfound")

    assert str(exc.value) == "restore not found"


@pytest.mark.asyncio
async def test_create_restore_success(
    async_client, restore_body, restore_model_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=202,
        json=restore_model_mock,
    )

    response = await async_client.create_restore(body=restore_body)

    assert isinstance(response, Restore)
    assert "/v2/databases/orders-db/restores/" in mock_post.call_args.kwargs["url"]


@pytest.mark.asyncio
async def test_create_restore_migration_source(
    async_client, restore_migration_body, restore_model_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=202,
        json=restore_model_mock,
    )

    await async_client.create_restore(body=restore_migration_body)

    sent = mock_post.call_args.kwargs["json"]
    assert sent["spec"]["source"]["type"] == "dataDirectory"
    assert sent["spec"]["source"]["sourceVersion"] == "17"


@pytest.mark.asyncio
async def test_create_restore_requires_target_database(async_client, mocker: MockFixture):
    mocker.patch("httpx.AsyncClient.post")

    body = {
        "metadata": {"name": "orphan-restore"},
        "spec": {"source": {"type": "backup", "backupName": "orders-nightly"}},
    }

    with pytest.raises(ValueError):
        await async_client.create_restore(body=body)


@pytest.mark.asyncio
async def test_delete_restore_success(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    response = await async_client.delete_restore(
        database="orders-db", name="orders-db-restore"
    )

    assert response is None
