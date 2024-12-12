import httpx
import pytest
import pytest_asyncio  # noqa: F401
from munch import Munch
from asyncmock import AsyncMock

from tests.data.mock_data import deployment_body  # noqa: F401
from tests.utils.fixtures import async_client as client  # noqa: F401


@pytest.mark.asyncio
async def test_list_deployments_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get") method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-deployment", "guid": "mock_deployment_guid"}],
        },
    )

    # Call the list_deployments method
    response = await client.list_deployments()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [
        {"name": "test-deployment", "guid": "mock_deployment_guid"}
    ]


@pytest.mark.asyncio
async def test_list_deployments_not_found(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get") method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        await client.list_deployments()

    assert str(exc.value) == "not found"


@pytest.mark.asyncio
async def test_get_deployment_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get") method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Deployment",
            "metadata": {"guid": "test_deployment_guid", "name": "test_deployment"},
        },
    )

    # Call the get_deployment method
    response = await client.get_deployment(name="mock_deployment_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "test_deployment_guid"


@pytest.mark.asyncio
async def test_get_deployment_not_found(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get") method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "deployment not found"},
    )

    # Call the get_deployment method
    with pytest.raises(Exception) as exc:
        await client.get_deployment(name="mock_deployment_name")

    assert str(exc.value) == "deployment not found"


@pytest.mark.asyncio
async def test_create_deployment_success(client, deployment_body, mocker: AsyncMock):  # noqa: F811
    mock_post = mocker.patch("httpx.AsyncClient.post")

    mock_post.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Deployment",
            "metadata": {"guid": "test_deployment_guid", "name": "test_deployment"},
        },
    )

    response = await client.create_deployment(body=deployment_body)

    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "test_deployment_guid"


@pytest.mark.asyncio
async def test_create_deployment_unauthorized(client, deployment_body, mocker: AsyncMock):  # noqa: F811
    mock_post = mocker.patch("httpx.AsyncClient.post")

    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        await client.create_deployment(body=deployment_body)

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_update_deployment_success(client, deployment_body, mocker: AsyncMock):  # noqa: F811
    mock_put = mocker.patch("httpx.AsyncClient.put")

    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Deployment",
            "metadata": {"guid": "test_deployment_guid", "name": "test_deployment"},
        },
    )

    response = await client.update_deployment(
        name="mock_deployment_name", body=deployment_body
    )

    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "test_deployment_guid"


@pytest.mark.asyncio
async def test_delete_deployment_success(client, mocker: AsyncMock):  # noqa: F811
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await client.delete_deployment(name="mock_deployment_name")

    assert response["success"] is True
