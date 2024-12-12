import httpx
import pytest
from munch import Munch
from pytest_mock import MockFixture

from tests.data.mock_data import staticroute_body  # noqa: F401
from tests.utils.fixtures import client  # noqa: F401


def test_list_staticroutes_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-staticroute", "guid": "mock_staticroute_guid"}],
        },
    )

    # Call the list_staticroutes method
    response = client.list_staticroutes()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [
        {"name": "test-staticroute", "guid": "mock_staticroute_guid"}
    ]


def test_list_staticroutes_not_found(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        client.list_staticroutes()

    assert str(exc.value) == "not found"


def test_create_staticroute_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json={
            "metadata": {"guid": "test_staticroute_guid", "name": "test_staticroute"},
        },
    )

    # Call the create_staticroute method
    response = client.create_staticroute(body=staticroute_body)

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_staticroute_guid"


def test_create_staticroute_bad_request(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "already exists"},
    )

    with pytest.raises(Exception) as exc:
        client.create_staticroute(body=staticroute_body)

    assert str(exc.value) == "already exists"


def test_get_staticroute_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_staticroute_guid", "name": "test_staticroute"},
        },
    )

    # Call the get_staticroute method
    response = client.get_staticroute(name="mock_staticroute_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_staticroute_guid"


def test_update_staticroute_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"guid": "test_staticroute_guid", "name": "test_staticroute"},
        },
    )

    # Call the update_staticroute method
    response = client.update_staticroute(
        name="mock_staticroute_name", body=staticroute_body
    )

    # Validate the response
    assert isinstance(response, Munch)
    assert response.metadata.guid == "test_staticroute_guid"


def test_delete_staticroute_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_staticroute method
    response = client.delete_staticroute(name="mock_staticroute_name")

    # Validate the response
    assert response["success"] is True
