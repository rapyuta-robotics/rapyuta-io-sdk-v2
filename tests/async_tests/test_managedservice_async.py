import httpx
import pytest
from asyncmock import AsyncMock

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import (
    ManagedServiceBinding,
    ManagedServiceInstanceList,
    ManagedServiceBindingList,
    ManagedServiceInstance,
    ManagedServiceProvider,
    ManagedServiceProviderList,
)
from tests.utils.fixtures import async_client
from tests.data import (
    managedservice_binding_model_mock,
    managedservice_model_mock,
    managedservicebindinglist_model_mock,
    managedservicelist_model_mock,
)


@pytest.mark.asyncio
async def test_list_providers_success(async_client, mocker: AsyncMock):
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
    response = await async_client.list_providers()

    # Validate the response
    assert isinstance(response, ManagedServiceProviderList)
    assert isinstance(response.items[0], ManagedServiceProvider)
    assert response.items[0].name == "test-provider"


@pytest.mark.asyncio
async def test_list_instances_success(
    async_client, managedservicelist_model_mock, mocker: AsyncMock
):
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=managedservicelist_model_mock,
    )

    # Call the list_instances method
    response = await async_client.list_instances()

    # Validate the response
    assert isinstance(response, ManagedServiceInstanceList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    instance = response.items[0]
    assert instance.metadata.guid == "mock_instance_guid"
    assert instance.metadata.name == "test-instance"
    assert instance.kind == "ManagedServiceInstance"
    assert instance.spec.provider == "elasticsearch"
    assert instance.spec.config["version"] == "7.10"


@pytest.mark.asyncio
async def test_get_instance_success(
    async_client, managedservice_model_mock, mocker: AsyncMock
):
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=managedservice_model_mock,
    )

    # Call the get_instance method
    response = await async_client.get_instance(name="mock_instance_name")

    # Validate the response
    assert isinstance(response, ManagedServiceInstance)
    assert response.metadata.guid == "mock_instance_guid"
    assert response.metadata.name == "test-instance"
    assert response.kind == "ManagedServiceInstance"
    assert response.spec.provider == "elasticsearch"


@pytest.mark.asyncio
async def test_create_instance_success(
    async_client, managedservice_model_mock, mocker: AsyncMock
):
    # Mock the httpx.AsyncClient.post method
    mock_post = mocker.patch("httpx.AsyncClient.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=managedservice_model_mock,
    )

    # Call the create_instance method
    response = await async_client.create_instance(
        body={
            "apiVersion": "api.rapyuta.io/v2",
            "metadata": {
                "name": "test-instance",
            },
        }
    )

    # Validate the response
    assert isinstance(response, ManagedServiceInstance)
    assert response.metadata.guid == "mock_instance_guid"
    assert response.metadata.name == "test-instance"
    assert response.kind == "ManagedServiceInstance"


@pytest.mark.asyncio
async def test_delete_instance_success(async_client, mocker: AsyncMock):
    # Mock the httpx.AsyncClient.delete method
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_instance method
    response = await async_client.delete_instance(name="mock_instance_name")

    # Validate the response
    assert response is None


@pytest.mark.asyncio
async def test_list_instance_bindings_success(
    async_client, managedservicebindinglist_model_mock, mocker: AsyncMock
):
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=managedservicebindinglist_model_mock,
    )

    # Call the list_instance_bindings method
    response = await async_client.list_instance_bindings(
        instance_name="mock_instance_name"
    )

    # Validate the response
    assert isinstance(response, ManagedServiceBindingList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    binding = response.items[0]
    assert binding.metadata.guid == "mock_instance_binding_guid"
    assert binding.metadata.name == "test-instance-binding"
    assert binding.kind == "ManagedServiceBinding"
    assert binding.spec.provider == "headscalevpn"


@pytest.mark.asyncio
async def test_get_instance_binding_success(
    async_client, managedservice_binding_model_mock, mocker: AsyncMock
):
    # Mock the httpx.AsyncClient.get method
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=managedservice_binding_model_mock,
    )

    # Call the get_instance_binding method
    response = await async_client.get_instance_binding(
        name="test-instance-binding", instance_name="mock_instance_name"
    )

    # Validate the response
    assert isinstance(response, ManagedServiceBinding)
    assert response.metadata.guid == "mock_instance_binding_guid"
    assert response.metadata.name == "test-instance-binding"
    assert response.kind == "ManagedServiceBinding"
    assert response.spec.provider == "headscalevpn"


@pytest.mark.asyncio
async def test_create_instance_binding_success(
    async_client, managedservice_binding_model_mock, mocker: AsyncMock
):
    # Mock the httpx.AsyncClient.post method
    mock_post = mocker.patch("httpx.AsyncClient.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=managedservice_binding_model_mock,
    )

    # Call the create_instance_binding method
    response = await async_client.create_instance_binding(
        body={
            "metadata": {
                "name": "test-instance-binding",
                "labels": {},
            },
            "spec": {
                "instance": "vpn_instance_value",
                "provider": "headscalevpn",
            },
        },
        instance_name="mock_instance_name",
    )

    # Validate the response
    assert isinstance(response, ManagedServiceBinding)
    assert response.metadata.guid == "mock_instance_binding_guid"
    assert response.metadata.name == "test-instance-binding"
    assert response.kind == "ManagedServiceBinding"


@pytest.mark.asyncio
async def test_delete_instance_binding_success(async_client, mocker: AsyncMock):
    # Mock the httpx.AsyncClient.delete method
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_instance_binding method
    response = await async_client.delete_instance_binding(
        name="mock_instance_binding_name", instance_name="mock_instance_name"
    )

    # Validate the response
    assert response is None
