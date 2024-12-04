import httpx
import pytest  # noqa: F401
from munch import Munch
from pytest_mock import MockerFixture

from tests.utils.fixtures import client  # noqa: F401


def test_list_providers_success(client, mocker: MockerFixture):  # noqa: F811
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

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the list_providers method
    response = client.list_providers()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test-provider", "guid": "mock_provider_guid"}]


def test_list_instances_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-instance", "guid": "mock_instance_guid"}],
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the list_instances method
    response = client.list_instances()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test-instance", "guid": "mock_instance_guid"}]


def test_get_instance_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_instance_guid", "name": "test_instance"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the get_instance method
    response = client.get_instance(name="mock_instance_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_instance_guid"


def test_create_instance_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_instance_guid", "name": "test_instance"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the create_instance method
    response = client.create_instance(body={"name": "test_instance"})

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_instance_guid"


def test_delete_instance_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the delete_instance method
    response = client.delete_instance(name="mock_instance_name")

    # Validate the response
    assert response["success"] is True


def test_list_instance_bindings_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

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

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the list_instance_bindings method
    response = client.list_instance_bindings("mock_instance_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [
        {"name": "test-instance-binding", "guid": "mock_instance_binding_guid"}
    ]


def test_get_instance_binding_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

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

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the get_instance_binding method
    response = client.get_instance_binding(
        name="mock_instance_binding_name", instance_name="mock_instance_name"
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_instance_binding_guid"


def test_create_instance_binding_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

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

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the create_instance_binding method
    response = client.create_instance_binding(
        body={"name": "test_instance_binding"}, instance_name="mock_instance_name"
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_instance_binding_guid"


def test_delete_instance_binding_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the delete_instance_binding method
    response = client.delete_instance_binding(
        name="mock_instance_binding_name", instance_name="mock_instance_name"
    )

    # Validate the response
    assert response["success"] is True
