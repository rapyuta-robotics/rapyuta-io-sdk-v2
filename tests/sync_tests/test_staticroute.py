import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import StaticRoute, StaticRouteList
from tests.utils.fixtures import client
from tests.data.mock_data import (
    staticroutelist_model_mock as staticroutelist_model_mock,
    staticroute_model_mock as staticroute_model_mock,
    staticroute_body as staticroute_body,
)


def test_list_staticroutes_success(
    client, staticroutelist_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=staticroutelist_model_mock,
    )

    # Call the list_staticroutes method
    response = client.list_staticroutes()

    # Validate the response
    assert isinstance(response, StaticRouteList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    staticroute = response.items[0]
    assert staticroute.metadata.guid == "staticroute-aaaaaaaaaaaaaaaaaaaa"
    assert staticroute.metadata.name == "test-staticroute"
    assert staticroute.kind == "StaticRoute"


def test_list_staticroutes_not_found(client, mocker: MockFixture):
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


def test_create_staticroute_success(
    client, staticroute_body, staticroute_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=staticroute_model_mock,
    )

    # Call the create_staticroute method
    response = client.create_staticroute(body=staticroute_body)

    # Validate the response
    assert isinstance(response, StaticRoute)
    assert response.metadata.guid == "staticroute-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test-staticroute"


def test_create_staticroute_bad_request(client, staticroute_body, mocker: MockFixture):
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


def test_get_staticroute_success(client, staticroute_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=staticroute_model_mock,
    )

    # Call the get_staticroute method
    response = client.get_staticroute(name="mock_staticroute_name")

    # Validate the response
    assert isinstance(response, StaticRoute)
    assert response.metadata.guid == "staticroute-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test-staticroute"


def test_update_staticroute_success(
    client, staticroute_body, staticroute_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=staticroute_model_mock,
    )

    # Call the update_staticroute method
    response = client.update_staticroute(
        name="mock_staticroute_name", body=staticroute_body
    )

    # Validate the response
    assert isinstance(response, StaticRoute)
    assert response.metadata.guid == "staticroute-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test-staticroute"


def test_delete_staticroute_success(client, mocker: MockFixture):
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
    assert response is None
