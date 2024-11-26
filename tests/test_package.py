import httpx
import pytest
from munch import Munch
from pytest_mock import MockerFixture

from tests.utils.test_util import (
    client,  # noqa: F401
    mock_response,  # noqa: F401
    package_body,  # noqa: F401
)


def test_list_packages_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test_package", "guid": "mock_package_guid"}],
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

    # Call the list_packages method
    response = client.list_packages()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test_package", "guid": "mock_package_guid"}]


def test_list_packages_not_found(client, mocker: MockerFixture):  # noqa: F811
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

    # Call the list_packages method
    with pytest.raises(Exception) as exc:
        client.list_packages()

    # Validate the exception message
    assert str(exc.value) == "not found"
    # assert response. == "not found"


def test_get_package_success(client, mock_response, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_package_guid", "name": "test_package"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the get_package method
    response = client.get_package(name="mock_package_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_package_guid"
    assert response.metadata.name == "test_package"


def test_get_package_not_found(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True, **kwargs: {
        "Authorization": f"Bearer {client.auth_token}",
        "organizationguid": client.organization_guid,
        "project": kwargs.get("package_guid") if with_project else None,
    }

    # Call the get_package method
    with pytest.raises(Exception) as exc:
        client.get_package(name="mock_package_name")

    # Validate the exception message
    assert str(exc.value) == "not found"


def test_create_package_success(client, package_body, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_package_guid", "name": "test_package"},
        },
    )

    # Override get_headers to return the mocked headers without None values
    client.config.get_headers = lambda with_project=True, **kwargs: {
        k: v
        for k, v in {
            "Authorization": f"Bearer {client.auth_token}",
            "organizationguid": client.organization_guid,
            "project": kwargs.get("project_guid") if with_project else None,
        }.items()
        if v is not None
    }

    # Call the create_package method
    response = client.create_package(body={"name": "test_package"})

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_package_guid"
    assert response.metadata.name == "test_package"
