import httpx
import pytest
from munch import Munch
from pytest_mock import MockerFixture

from tests.utils.util import secret_body  # noqa: F401
from tests.utils.fixtures import client  # noqa: F401


def test_list_secrets_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-secret", "guid": "mock_secret_guid"}],
        },
    )

    # Override get_headers to return mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the list_secrets method
    response = client.list_secrets()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test-secret", "guid": "mock_secret_guid"}]


def test_list_secrets_not_found(client, mocker: MockerFixture):  # noqa: F811
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
        client.list_secrets()

    assert str(exc.value) == "not found"


def test_create_secret_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_secret_guid", "name": "test_secret"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": "mock_project_guid" if with_project else None,
    }

    # Call the create_secret method
    response = client.create_secret(secret_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_secret_guid"


def test_create_secret_already_exists(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "secret already exists"},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": "mock_project_guid" if with_project else None,
    }

    with pytest.raises(Exception) as exc:
        client.create_secret(secret_body)

    assert str(exc.value) == "secret already exists"


def test_update_secret_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_secret_guid", "name": "test_secret"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": "mock_project_guid" if with_project else None,
    }

    # Call the update_secret method
    response = client.update_secret("mock_secret_guid", body=secret_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_secret_guid"


def test_delete_secret_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": "mock_project_guid" if with_project else None,
    }

    # Call the delete_secret method
    response = client.delete_secret("mock_secret_guid")

    # Validate the response
    assert response == {"success": True}


def test_get_secret_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_secret_guid", "name": "test_secret"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": "mock_project_guid" if with_project else None,
    }

    # Call the get_secret method
    response = client.get_secret("mock_secret_guid")

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_secret_guid"
    assert response.metadata.name == "test_secret"
