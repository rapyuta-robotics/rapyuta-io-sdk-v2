from pytest_mock import MockerFixture
from munch import Munch
import httpx
from tests.utils.test_util import client, mock_response  # noqa: F401
import pytest


def test_list_packages_success(client, mocker: MockerFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={"metadata": {"name": "test_package", "guid": "mock_package_guid"}},
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
