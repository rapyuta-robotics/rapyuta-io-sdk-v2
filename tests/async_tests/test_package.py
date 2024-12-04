import pytest
import pytest_asyncio  # noqa: F401
import httpx
from munch import Munch
from asyncmock import AsyncMock

from tests.utils.test_util import (
    async_client as client,  # noqa: F401
    package_body,
)


@pytest.mark.asyncio
async def test_list_packages_success(client, mocker: AsyncMock):  # noqa: F811
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test_package", "guid": "mock_package_guid"}],
        },
    )

    response = await client.list_packages()

    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test_package", "guid": "mock_package_guid"}]


@pytest.mark.asyncio
async def test_list_packages_not_found(client, mocker: AsyncMock):  # noqa: F811
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        await client.list_packages()
    assert str(exc.value) == "not found"


@pytest.mark.asyncio
async def test_create_package_success(client, mocker: AsyncMock):  # noqa: F811
    mock_post = mocker.patch("httpx.AsyncClient.post")

    mock_post.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Package",
            "metadata": {"name": "test-package", "guid": "mock_package_guid"},
            "spec": {
                "users": [{"userGUID": "mock_user_guid", "emailID": "mock_email"}]
            },
        },
    )

    response = await client.create_package(package_body)

    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "mock_package_guid"
