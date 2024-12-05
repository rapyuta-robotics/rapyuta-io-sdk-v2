import httpx
import pytest
import pytest_asyncio  # noqa: F401
from munch import Munch
from asyncmock import AsyncMock

from tests.data.mock_data import network_body  # noqa: F401
from tests.utils.fixtures import async_client as client  # noqa: F401


@pytest.mark.asyncio
async def test_list_networks_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-network", "guid": "mock_network_guid"}],
        },
    )

    # Call the list_networks method
    response = await client.list_networks()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test-network", "guid": "mock_network_guid"}]


@pytest.mark.asyncio
async def test_list_networks_not_found(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        await client.list_networks()

    assert str(exc.value) == "not found"


@pytest.mark.asyncio
async def test_create_network_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.post method
    mock_post = mocker.patch("httpx.AsyncClient.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "mock_network_guid", "name": "test-network"},
        },
    )

    # Call the create_network method
    response = await client.create_network(body=network_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["name"] == "test-network"


@pytest.mark.asyncio
async def test_create_network_failure(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.post method
    mock_post = mocker.patch("httpx.AsyncClient.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "already exists"},
    )

    with pytest.raises(Exception) as exc:
        await client.create_network(body=network_body)

    assert str(exc.value) == "already exists"


@pytest.mark.asyncio
async def test_get_network_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "mock_network_guid", "name": "test-network"},
        },
    )

    # Call the get_network method
    response = await client.get_network(name="test-network")

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "mock_network_guid"


@pytest.mark.asyncio
async def test_delete_network_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.delete method
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_network method
    response = await client.delete_network(name="test-network")

    # Validate the response
    assert response["success"] is True
