import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import PackageList, Package
from tests.utils.fixtures import async_client
from tests.data import (
    package_body,
    cloud_package_model_mock,
    device_package_model_mock,
    packagelist_model_mock,
)


@pytest.mark.asyncio
async def test_list_packages_success(
    async_client, packagelist_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=packagelist_model_mock,
    )

    response = await async_client.list_packages()

    assert isinstance(response, PackageList)
    assert len(response.items) == 2
    assert response.items[0].metadata.name == "gostproxy"
    assert response.items[1].metadata.name == "database"


@pytest.mark.asyncio
async def test_get_cloud_package_success(
    async_client, cloud_package_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=cloud_package_model_mock,
    )
    response = await async_client.get_package(name="gostproxy")
    assert isinstance(response, Package)
    assert response.metadata.name == "gostproxy"


@pytest.mark.asyncio
async def test_get_device_package_success(
    async_client, device_package_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=device_package_model_mock,
    )
    response = await async_client.get_package(name="database")
    assert isinstance(response, Package)
    assert response.metadata.name == "database"


@pytest.mark.asyncio
async def test_get_package_not_found(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "package not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.get_package(name="notfound")

    assert str(exc.value) == "package not found"


@pytest.mark.asyncio
async def test_create_package_unauthorized(
    async_client, package_body, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.create_package(body=package_body)

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_delete_package_success(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await async_client.delete_package(name="gostproxy", version="v1.0.0")

    assert response is None
