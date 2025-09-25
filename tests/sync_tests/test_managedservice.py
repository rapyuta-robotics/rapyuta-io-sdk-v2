import httpx
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.pydantic_models import ManagedService, ManagedServiceList
from tests.utils.fixtures import client
from tests.data import (
    managedservice_binding_model_mock,
    managedservice_model_mock,
    managedservicebindinglist_model_mock,
    managedservicelist_model_mock,
)


def test_list_providers_success(client, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-provider", "guid": "mock_provider_guid"}],
        },
    )

    # Call the list_providers method
    response = client.list_providers()

    # Validate the response
    assert response["items"] == [{"name": "test-provider", "guid": "mock_provider_guid"}]


def test_list_instances_success(
    client, managedservicelist_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=managedservicelist_model_mock,
    )

    # Call the list_instances method
    response = client.list_instances()

    # Validate the response
    assert isinstance(response, ManagedServiceList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    instance = response.items[0]
    assert instance.metadata.guid == "mock_instance_guid"
    assert instance.metadata.name == "test-instance"
    assert instance.kind == "ManagedServiceInstance"
    assert instance.spec.provider == "elasticsearch"
    assert instance.spec.config["version"] == "7.10"


def test_get_instance_success(client, managedservice_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=managedservice_model_mock,
    )

    # Call the get_instance method
    response = client.get_instance(name="mock_instance_name")

    # Validate the response
    assert response["metadata"]["guid"] == "mock_instance_guid"
    assert response["metadata"]["name"] == "test-instance"
    assert response["kind"] == "ManagedServiceInstance"
    assert response["spec"]["provider"] == "elasticsearch"


def test_create_instance_success(client, managedservice_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=managedservice_model_mock,
    )

    # Call the create_instance method
    response = client.create_instance(body={"name": "test_instance"})

    # Validate the response
    assert response["metadata"]["guid"] == "mock_instance_guid"
    assert response["metadata"]["name"] == "test-instance"
    assert response["kind"] == "ManagedServiceInstance"


def test_delete_instance_success(client, mocker: MockFixture):
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_instance method
    response = client.delete_instance(name="mock_instance_name")

    # Validate the response
    assert response is None


def test_list_instance_bindings_success(
    client, managedservicebindinglist_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=managedservicebindinglist_model_mock,
    )

    # Call the list_instance_bindings method
    response = client.list_instance_bindings("mock_instance_name")

    # Validate the response
    assert response["metadata"]["continue"] == 1
    assert len(response["items"]) == 1
    binding = response["items"][0]
    assert binding["metadata"]["guid"] == "mock_instance_binding_guid"
    assert binding["metadata"]["name"] == "test-instance-binding"
    assert binding["kind"] == "ManagedServiceBinding"
    assert binding["spec"]["provider"] == "headscalevpn"


def test_get_instance_binding_success(
    client, managedservice_binding_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=managedservice_binding_model_mock,
    )

    # Call the get_instance_binding method
    response = client.get_instance_binding(
        name="mock_instance_binding_name", instance_name="mock_instance_name"
    )

    # Validate the response
    assert response["metadata"]["guid"] == "mock_instance_binding_guid"
    assert response["metadata"]["name"] == "test-instance-binding"
    assert response["kind"] == "ManagedServiceBinding"
    assert response["spec"]["provider"] == "headscalevpn"


def test_create_instance_binding_success(
    client, managedservice_binding_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=managedservice_binding_model_mock,
    )

    # Call the create_instance_binding method
    response = client.create_instance_binding(
        body={"name": "test_instance_binding"}, instance_name="mock_instance_name"
    )

    # Validate the response
    assert response["metadata"]["guid"] == "mock_instance_binding_guid"
    assert response["metadata"]["name"] == "test-instance-binding"
    assert response["kind"] == "ManagedServiceBinding"


def test_delete_instance_binding_success(client, mocker: MockFixture):
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_instance_binding method
    response = client.delete_instance_binding(
        name="mock_instance_binding_name", instance_name="mock_instance_name"
    )

    # Validate the response
    assert response["success"] is True
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "apiVersion": "api.rapyuta.io/v2",
            "kind": "ManagedServiceBinding",
            "metadata": {
                "guid": "test_instance_binding_guid",
                "name": "test_instance_binding",
                "creatorGUID": "creator-guid",
                "projectGUID": "project-aaaaaaaaaaaaaaaaaaaa",
                "labels": {"env": "test"},
            },
            "spec": {
                "provider": "headscalevpn",
                "config": {"version": "1.0"},
            },
        },
    )

    # Call the get_instance_binding method
    response = client.get_instance_binding(
        name="mock_instance_binding_name", instance_name="mock_instance_name"
    )

    # Validate the response
    assert isinstance(response, ManagedService)
    assert response.metadata.guid == "test_instance_binding_guid"
    assert response.metadata.name == "test_instance_binding"
    assert response.kind == "ManagedServiceBinding"
    assert response.spec.provider == "headscalevpn"


def test_create_instance_binding_success(
    client, managedservice_binding_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=managedservice_binding_model_mock,
    )

    # Call the create_instance_binding method
    response = client.create_instance_binding(
        body={
            "metadata": {
                "name": "test-instance-binding",
                "labels": {},
            },
            "spec": {
                "instance": "vpn_instance_value",
                "provider": "headscalevpn",
                "throwaway": False,
                "config": {
                    "ephemeral": False,
                    "expirationTime": "2024-12-31T23:59:59Z",
                    "nodeKey": "machine_value",
                },
            },
        },
        instance_name="mock_instance_name",
    )

    # Validate the response
    assert response["metadata"]["guid"] == "mock_instance_binding_guid"
    assert response["metadata"]["name"] == "test-instance-binding"
    assert response["kind"] == "ManagedServiceBinding"


def test_delete_instance_binding_success(client, mocker: MockFixture):
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_instance_binding method
    response = client.delete_instance_binding(
        name="mock_instance_binding_name", instance_name="mock_instance_name"
    )

    # Validate the response
    assert response is None
