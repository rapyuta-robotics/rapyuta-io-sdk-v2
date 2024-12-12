import httpx
import pytest  # noqa: F401
from munch import Munch
from asyncmock import AsyncMock

from tests.utils.fixtures import async_client as client  # noqa: F401


@pytest.mark.asyncio
async def test_list_providers_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-provider", "guid": "mock_provider_guid"}],
        },
    )

    # Call the list_providers method
    response = await client.list_providers()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test-provider", "guid": "mock_provider_guid"}]


@pytest.mark.asyncio
async def test_list_instances_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-instance", "guid": "mock_instance_guid"}],
        },
    )

    # Call the list_instances method
    response = await client.list_instances()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test-instance", "guid": "mock_instance_guid"}]


@pytest.mark.asyncio
async def test_get_instance_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_instance_guid", "name": "test_instance"},
        },
    )

    # Call the get_instance method
    response = await client.get_instance(name="mock_instance_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_instance_guid"


@pytest.mark.asyncio
async def test_create_instance_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.post method
    mock_post = mocker.patch("httpx.AsyncClient.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_instance_guid", "name": "test_instance"},
        },
    )

    # Call the create_instance method
    response = await client.create_instance(body={"name": "test_instance"})

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_instance_guid"


@pytest.mark.asyncio
async def test_delete_instance_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.delete method
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_instance method
    response = await client.delete_instance(name="mock_instance_name")

    # Validate the response
    assert response["success"] is True


@pytest.mark.asyncio
async def test_list_instance_bindings_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [
                {"name": "test-instance-binding", "guid": "mock_instance_binding_guid"}
            ],
        },
    )

    # Call the list_instance_bindings method
    response = await client.list_instance_bindings("mock_instance_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [
        {"name": "test-instance-binding", "guid": "mock_instance_binding_guid"}
    ]


@pytest.mark.asyncio
async def test_get_instance_binding_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {
                "guid": "test_instance_binding_guid",
                "name": "test_instance_binding",
            },
        },
    )

    # Call the get_instance_binding method
    response = await client.get_instance_binding(
        name="mock_instance_binding_name", instance_name="mock_instance_name"
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_instance_binding_guid"


@pytest.mark.asyncio
async def test_create_instance_binding_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.post method
    mock_post = mocker.patch("httpx.AsyncClient.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {
                "guid": "test_instance_binding_guid",
                "name": "test_instance_binding",
            },
        },
    )

    # Call the create_instance_binding method
    response = await client.create_instance_binding(
        body={"name": "test_instance_binding"}, instance_name="mock_instance_name"
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_instance_binding_guid"


@pytest.mark.asyncio
async def test_delete_instance_binding_success(client, mocker: AsyncMock):  # noqa: F811
    # Mock the httpx.AsyncClient.delete method
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_instance_binding method
    response = await client.delete_instance_binding(
        name="mock_instance_binding_name", instance_name="mock_instance_name"
    )

    # Validate the response
    assert response["success"] is True
