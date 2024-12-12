import httpx
import pytest
from munch import Munch
from pytest_mock import MockFixture

from tests.data.mock_data import disk_body  # noqa: F401
from tests.utils.fixtures import client  # noqa: F401


def test_list_disks_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-disk", "guid": "mock_disk_guid"}],
        },
    )

    # Call the list_disks method
    response = client.list_disks()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test-disk", "guid": "mock_disk_guid"}]


def test_list_disks_not_found(client, mocker: MockFixture):  # noqa: F811
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


def test_get_disk_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Disk",
            "metadata": {"guid": "test_disk_guid", "name": "mock_disk_name"},
        },
    )

    # Call the get_disk method
    response = client.get_disk(name="mock_disk_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "test_disk_guid"


def test_get_disk_not_found(client, mocker: MockFixture):  # noqa: F811
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


def test_create_disk_success(client, disk_body, mocker: MockFixture):  # noqa: F811
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Disk",
            "metadata": {"guid": "test_disk_guid", "name": "test_disk"},
        },
    )

    response = client.create_disk(body=disk_body, project_guid="mock_project_guid")

    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_disk_guid"
    assert response.metadata.name == "test_disk"


def test_delete_disk_success(client, mocker: MockFixture):  # noqa: F811
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
    assert response["success"] is True


def test_delete_disk_not_found(client, mocker: MockFixture):  # noqa: F811
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
