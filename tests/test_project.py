from pytest_mock import MockerFixture
from munch import Munch
import httpx
from tests.utils.test_util import client, mock_response  # noqa: F401
import pytest


# Test function for list_projects
def test_list_projects_success(client, mock_response, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=mock_response,
    )

    # Override get_headers to return the mocked headers without None values
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
    assert response.name == "test_project"
    
def test_list_projects_unauthorized(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized permission access"},
    )

    # Override get_headers to return the mocked headers without None values
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
    with pytest.raises(Exception) as exc:
        client.list_projects()

    # Validate the exception message
    assert str(exc.value) == "not found"
    
def test_list_packages_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={"metadata": {"name": "test_package", "guid": "mock_package_guid"}},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the list_packages method
    response = client.list_packages("mock_project_guid")

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.name == "test_package"
    
def test_list_packages_not_found(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": "mock_project_guid" if with_project else None,
        }.items()
        if v is not None
    }

    # Call the list_packages method
    with pytest.raises(Exception) as exc:
        client.list_packages("mock_project_guid")

    # Validate the exception message
    assert str(exc.value) == "not found"
