import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import Disk, DiskList
from tests.data.mock_data import disk_body, disk_model_mock, disklist_model_mock
from tests.utils.fixtures import client


def test_list_disks_success(client, disklist_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=disklist_model_mock,
    )

    # Call the list_disks method
    response = client.list_disks()

    # Validate the response
    assert isinstance(response, DiskList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    disk = response.items[0]
    assert disk.metadata.guid == "disk-mockdisk123456789101"
    assert disk.metadata.name == "mock_disk_1"
    assert disk.kind == "Disk"


def test_list_disks_not_found(client, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        client.list_disks()

    assert str(exc.value) == "not found"


def test_get_disk_success(client, disk_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=disk_model_mock,
    )

    # Call the get_disk method
    response = client.get_disk(name="mock_disk_name")

    # Validate the response
    assert isinstance(response, Disk)
    assert response.metadata.guid == "disk-mockdisk123456789101"
    assert response.metadata.name == "mock_disk_1"


def test_get_disk_not_found(client, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "disk not found"},
    )

    # Call the get_disk method
    with pytest.raises(Exception) as exc:
        client.get_disk(name="mock_disk_name")

    assert str(exc.value) == "disk not found"


def test_create_disk_success(client, disk_body, disk_model_mock, mocker: MockFixture):
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=200,
        json=disk_model_mock,
    )

    response = client.create_disk(body=disk_body, project_guid="mock_project_guid")

    assert isinstance(response, Disk)
    assert response.metadata.guid == "disk-mockdisk123456789101"
    assert response.metadata.name == "mock_disk_1"


def test_delete_disk_success(client, mocker: MockFixture):
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_disk method
    response = client.delete_disk(name="mock_disk_name")

    # Validate the response
    assert response is None


def test_delete_disk_not_found(client, mocker: MockFixture):
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=404,
        json={"error": "disk not found"},
    )

    # Call the delete_disk method
    with pytest.raises(Exception) as exc:
        client.delete_disk(name="mock_disk_name")

    assert str(exc.value) == "disk not found"
