import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import Network, NetworkList
from tests.data.mock_data import network_body, network_model_mock, networklist_model_mock
from tests.utils.fixtures import client


def test_list_networks_success(client, networklist_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=networklist_model_mock,
    )

    # Call the list_networks method
    response = client.list_networks()

    # Validate the response
    assert isinstance(response, NetworkList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    network = response.items[0]
    assert network.metadata.guid == "network-aaaaaaaaaaaaaaaaaaaa"
    assert network.metadata.name == "test-network"
    assert network.kind == "Network"
    assert network.spec.runtime == "cloud"
    assert network.status.phase == "InProgress"
    assert network.status.status == "Running"


def test_list_networks_not_found(client, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        client.list_networks()

    assert str(exc.value) == "not found"


def test_get_network_success(client, network_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=network_model_mock,
    )

    # Call the get_network method
    response = client.get_network(name="test-network")

    # Validate the response
    assert isinstance(response, Network)
    assert response.metadata.guid == "network-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test-network"
    assert response.spec.runtime == "cloud"
    assert response.status.phase == "InProgress"
    assert response.status.status == "Running"


def test_create_network_success(
    client, network_body, network_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=network_model_mock,
    )

    # Call the create_network method
    response = client.create_network(body=network_body)

    # Validate the response
    assert isinstance(response, Network)
    assert response.metadata.guid == "network-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test-network"


def test_create_network_failure(client, network_body, mocker: MockFixture):
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "already exists"},
    )

    with pytest.raises(Exception) as exc:
        client.create_network(body=network_body)

    assert str(exc.value) == "already exists"


def test_delete_network_success(client, mocker: MockFixture):
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_network method
    response = client.delete_network(name="test-network")

    # Validate the response
    assert response is None
