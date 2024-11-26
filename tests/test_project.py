import httpx
import pytest
from munch import Munch
from pytest_mock import MockerFixture

from tests.utils.test_util import (
    client,
    mock_response,  # noqa: F401
    project_body,
)


# Test function for list_projects
def test_list_projects_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-project", "guid": "mock_project_guid"}],
        },
    )

    # Override get_headers to return mocked headers without None values
    client.config.get_headers = lambda with_project: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the list_projects method
    response = client.list_projects()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test-project", "guid": "mock_project_guid"}]


def test_list_projects_unauthorized(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized permission access"},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=False, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the list_projects method
    with pytest.raises(Exception) as exc:
        client.list_projects()

    # Validate the exception message
    assert str(exc.value) == "unauthorized permission access"


def test_list_projects_not_found(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=False, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the list_projects method
    with pytest.raises(Exception) as exc:
        client.list_projects()

    # Validate the exception message
    assert str(exc.value) == "not found"


def test_get_project_success(client, mock_response, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Project",
            "metadata": {"guid": "test_project_guid", "name": "test_project"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=False, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the get_project method
    response = client.get_project(project_guid="mock_project_guid")

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "test_project_guid"


def test_get_project_not_found(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "project not found"},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=False, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the get_project method
    with pytest.raises(Exception) as exc:
        client.get_project(project_guid="mock_project_guid")

    # Validate the exception message
    assert str(exc.value) == "project not found"


def test_create_project_success(client, mock_response, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=mock_response,
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=False, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the create_project method
    response = client.create_project(body=project_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "mock_project_guid"


def test_create_project_unauthorized(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized permission access"},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=False, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the create_project method
    with pytest.raises(Exception) as exc:
        client.create_project(body=project_body)

    # Validate the exception message
    assert str(exc.value) == "unauthorized permission access"


def test_update_project_success(client, mock_response, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=mock_response,
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=False, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the update_project method
    response = client.update_project(
        project_guid="mock_project_guid", body=project_body
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "mock_project_guid"


def test_delete_project_success(client, mock_response, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(status_code=200, json={"success": True})

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=False, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the delete_project method
    response = client.delete_project(project_guid="mock_project_guid")

    # Validate the response
    assert response["success"] is True
