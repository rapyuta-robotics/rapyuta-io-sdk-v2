import httpx
import pytest
from munch import Munch
from pytest_mock import MockerFixture

from tests.utils.util import network_body  # noqa: F401
from tests.utils.fixtures import client  # noqa: F401


def test_list_networks_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-network", "guid": "mock_network_guid"}],
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

    # Call the list_networks method
    response = client.list_networks()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test-network", "guid": "mock_network_guid"}]


def test_list_networks_not_found(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": "mock_project_guid" if with_project else None,
    }

    with pytest.raises(Exception) as exc:
        client.list_networks()

    assert str(exc.value) == "not found"


def test_create_network_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "mock_network_guid", "name": "test-network"},
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

    # Call the create_network method
    response = client.create_network(body=network_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["name"] == "test-network"


def test_create_network_failure(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "already exists"},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": "mock_project_guid" if with_project else None,
    }

    with pytest.raises(Exception) as exc:
        client.create_network(body=network_body)

    assert str(exc.value) == "already exists"


def test_get_network_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "mock_network_guid", "name": "test-network"},
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

    # Call the get_network method
    response = client.get_network(name="test-network")

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "mock_network_guid"


def test_delete_network_success(client, mocker: MockerFixture):  # noqa: F811
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

    # Call the delete_network method
    response = client.delete_network(name="test-network")

    # Validate the response
    assert response["success"] is True
