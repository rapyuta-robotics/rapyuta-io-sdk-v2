import httpx
import pytest
from munch import Munch
from asyncmock import AsyncMock

from tests.data.mock_data import staticroute_body  # noqa: F401
from tests.utils.fixtures import async_client as client  # noqa: F401


@pytest.mark.asyncio
async def test_list_staticroutes_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-staticroute", "guid": "mock_staticroute_guid"}],
        },
    )

    # Call the list_staticroutes method
    response = await client.list_staticroutes()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [
        {"name": "test-staticroute", "guid": "mock_staticroute_guid"}
    ]


@pytest.mark.asyncio
async def test_list_staticroutes_not_found(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        await client.list_staticroutes()

    assert str(exc.value) == "not found"


@pytest.mark.asyncio
async def test_create_staticroute_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.post method
    mock_post = mocker.patch("httpx.AsyncClient.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_staticroute_guid", "name": "test_staticroute"},
        },
    )

    # Call the create_staticroute method
    response = await client.create_staticroute(body=staticroute_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_staticroute_guid"


@pytest.mark.asyncio
async def test_create_staticroute_bad_request(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.post method
    mock_post = mocker.patch("httpx.AsyncClient.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "already exists"},
    )

    with pytest.raises(Exception) as exc:
        await client.create_staticroute(body=staticroute_body)

    assert str(exc.value) == "already exists"


@pytest.mark.asyncio
async def test_get_staticroute_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_staticroute_guid", "name": "test_staticroute"},
        },
    )

    # Call the get_staticroute method
    response = await client.get_staticroute(name="mock_staticroute_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_staticroute_guid"


@pytest.mark.asyncio
async def test_update_staticroute_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.put method
    mock_put = mocker.patch("httpx.AsyncClient.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_staticroute_guid", "name": "test_staticroute"},
        },
    )

    # Call the update_staticroute method
    response = await client.update_staticroute(
        name="mock_staticroute_name", body=staticroute_body
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_staticroute_guid"


@pytest.mark.asyncio
async def test_delete_staticroute_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.delete method
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_staticroute method
    response = await client.delete_staticroute(name="mock_staticroute_name")

    # Validate the response
    assert response["success"] is True
