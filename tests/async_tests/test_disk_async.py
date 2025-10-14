import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import DiskList, Disk
from tests.utils.fixtures import async_client
from tests.data import (
    disk_body,
    disk_model_mock,
    disklist_model_mock,
)


@pytest.mark.asyncio
async def test_list_disks_success(async_client, disklist_model_mock, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=disklist_model_mock,
    )

    response = await async_client.list_disks()

    assert isinstance(response, DiskList)
    assert len(response.items) == 1
    assert response.items[0].metadata.name == "mock_disk_1"


@pytest.mark.asyncio
async def test_get_disk_success(async_client, disk_model_mock, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=disk_model_mock,
    )
    response = await async_client.get_disk(name="mock_disk_1")
    assert isinstance(response, Disk)
    assert response.metadata.name == "mock_disk_1"


@pytest.mark.asyncio
async def test_get_disk_not_found(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "disk not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.get_disk(name="notfound")

    assert str(exc.value) == "disk not found"


@pytest.mark.asyncio
async def test_create_disk_unauthorized(async_client, disk_body, mocker: MockFixture):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.create_disk(body=disk_body)

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_delete_disk_success(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await async_client.delete_disk(name="mock_disk_1")

    assert response is None
