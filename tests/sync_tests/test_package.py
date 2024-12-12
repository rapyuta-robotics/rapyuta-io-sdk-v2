import httpx
import pytest
from munch import Munch
from pytest_mock import MockFixture

from tests.data.mock_data import package_body  # noqa: F401
from tests.utils.fixtures import client  # noqa: F401


def test_list_packages_success(client, mocker: MockFixture):  # noqa: F811
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

    # Call the list_packages method
    response = client.list_packages()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test_package", "guid": "mock_package_guid"}]


def test_list_packages_not_found(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    # Call the list_packages method
    with pytest.raises(Exception) as exc:
        client.list_packages()

    # Validate the exception message
    assert str(exc.value) == "not found"
    # assert response. == "not found"


def test_get_package_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_package_guid", "name": "test_package"},
        },
    )

    # Call the get_package method
    response = client.get_package(name="mock_package_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_package_guid"
    assert response.metadata.name == "test_package"


def test_get_package_not_found(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    # Call the get_package method
    with pytest.raises(Exception) as exc:
        client.get_package(name="mock_package_name")

    # Validate the exception message
    assert str(exc.value) == "not found"


def test_create_package_success(client, package_body, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_package_guid", "name": "test_package"},
        },
    )

    # Call the create_package method
    response = client.create_package(body=package_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_package_guid"
    assert response.metadata.name == "test_package"
