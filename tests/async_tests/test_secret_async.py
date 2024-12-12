import httpx
import pytest
import pytest_asyncio  # noqa: F401
from munch import Munch
from asyncmock import AsyncMock

from tests.data.mock_data import secret_body  # noqa: F401
from tests.utils.fixtures import async_client as client  # noqa: F401


@pytest.mark.asyncio
async def test_list_secrets_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-secret", "guid": "mock_secret_guid"}],
        },
    )

    # Call the list_secrets method
    response = await client.list_secrets()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test-secret", "guid": "mock_secret_guid"}]


@pytest.mark.asyncio
async def test_list_secrets_not_found(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        await client.list_secrets()

    assert str(exc.value) == "not found"


@pytest.mark.asyncio
async def test_create_secret_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.post method
    mock_post = mocker.patch("httpx.AsyncClient.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_secret_guid", "name": "test_secret"},
        },
    )

    # Call the create_secret method
    response = await client.create_secret(secret_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_secret_guid"


@pytest.mark.asyncio
async def test_create_secret_already_exists(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.post method
    mock_post = mocker.patch("httpx.AsyncClient.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "secret already exists"},
    )

    with pytest.raises(Exception) as exc:
        await client.create_secret(secret_body)

    assert str(exc.value) == "secret already exists"


@pytest.mark.asyncio
async def test_update_secret_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.put method
    mock_put = mocker.patch("httpx.AsyncClient.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_secret_guid", "name": "test_secret"},
        },
    )

    # Call the update_secret method
    response = await client.update_secret("mock_secret_guid", body=secret_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_secret_guid"


@pytest.mark.asyncio
async def test_delete_secret_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.delete method
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_secret method
    response = await client.delete_secret("mock_secret_guid")

    # Validate the response
    assert response == {"success": True}


@pytest.mark.asyncio
async def test_get_secret_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_secret_guid", "name": "test_secret"},
        },
    )

    # Call the get_secret method
    response = await client.get_secret("mock_secret_guid")

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_secret_guid"
    assert response.metadata.name == "test_secret"
