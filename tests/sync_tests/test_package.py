import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import Package, PackageList
from tests.utils.fixtures import client
from tests.data import (
    package_body,
    packagelist_model_mock,
    cloud_package_model_mock,
    device_package_model_mock,
)


def test_list_packages_success(client, packagelist_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=packagelist_model_mock,
    )

    # Call the list_packages method
    response = client.list_packages()

    # Validate the response
    assert isinstance(response, PackageList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 2
    cloud_pkg = response.items[0]
    device_pkg = response.items[1]
    assert cloud_pkg.metadata.guid == "pkg-aaaaaaaaaaaaaaaaaaaa"
    assert cloud_pkg.metadata.name == "gostproxy"
    assert cloud_pkg.kind == "Package"
    assert cloud_pkg.spec.runtime == "cloud"
    assert device_pkg.metadata.guid == "pkg-bbbbbbbbbbbbbbbbbbbb"
    assert device_pkg.metadata.name == "database"
    assert device_pkg.kind == "Package"
    assert device_pkg.spec.runtime == "device"


def test_list_packages_not_found(client, mocker: MockFixture):
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


def test_get_cloud_package_success(client, cloud_package_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=cloud_package_model_mock,
    )

    # Call the get_package method
    response = client.get_package(name="gostproxy")

    # Validate the response
    assert isinstance(response, Package)
    assert response.metadata.guid == "pkg-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "gostproxy"
    assert response.spec.runtime == "cloud"


def test_get_device_package_success(
    client, device_package_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=device_package_model_mock,
    )

    # Call the get_package method
    response = client.get_package(name="database")

    # Validate the response
    assert isinstance(response, Package)
    assert response.metadata.guid == "pkg-bbbbbbbbbbbbbbbbbbbb"
    assert response.metadata.name == "database"
    assert response.spec.runtime == "device"


def test_get_package_not_found(client, mocker: MockFixture):
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


def test_create_package_success(
    client, package_body, cloud_package_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=cloud_package_model_mock,
    )

    # Call the create_package method
    response = client.create_package(body=package_body)

    # Validate the response
    assert isinstance(response, Package)
    assert response.metadata.guid == "pkg-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "gostproxy"


def test_delete_package_success(client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.Client.delete")
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )
    response = client.delete_package(name="gostproxy", version="v1.0.0")
    assert response is None


def test_delete_package_not_found(client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.Client.delete")
    mock_delete.return_value = httpx.Response(
        status_code=404,
        json={"error": "package not found"},
    )
    with pytest.raises(Exception) as exc:
        client.delete_package(name="notfound", version="v1.0.0")
    assert str(exc.value) == "package not found"
