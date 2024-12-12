import httpx
import pytest
from munch import Munch
from pytest_mock import MockFixture

from tests.data.mock_data import deployment_body  # noqa: F401
from tests.utils.fixtures import client  # noqa: F401


def test_list_deployments_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-deployment", "guid": "mock_deployment_guid"}],
        },
    )

    # Call the list_deployments method
    response = client.list_deployments()

    # Validate the response
    assert isinstance(response, Munch)
    assert response["items"] == [
        {"name": "test-deployment", "guid": "mock_deployment_guid"}
    ]


def test_list_deployments_not_found(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        client.list_deployments()

    assert str(exc.value) == "not found"


def test_get_deployment_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Deployment",
            "metadata": {"guid": "test_deployment_guid", "name": "test_deployment"},
        },
    )

    # Call the get_deployment method
    response = client.get_deployment(name="mock_deployment_name")

    # Validate the response
    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "test_deployment_guid"


def test_get_deployment_not_found(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "deployment not found"},
    )

    # Call the get_deployment method
    with pytest.raises(Exception) as exc:
        client.get_deployment(name="mock_deployment_name")

    assert str(exc.value) == "deployment not found"


def test_create_deployment_success(client, deployment_body, mocker: MockFixture):  # noqa: F811
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Deployment",
            "metadata": {"guid": "test_deployment_guid", "name": "test_deployment"},
        },
    )

    response = client.create_deployment(body=deployment_body)

    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "test_deployment_guid"


def test_create_deployment_unauthorized(client, deployment_body, mocker: MockFixture):  # noqa: F811
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        client.create_deployment(body=deployment_body)

    assert str(exc.value) == "unauthorized"


def test_update_deployment_success(client, deployment_body, mocker: MockFixture):  # noqa: F811
    mock_put = mocker.patch("httpx.Client.put")

    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Deployment",
            "metadata": {"guid": "test_deployment_guid", "name": "test_deployment"},
        },
    )

    response = client.update_deployment(name="mock_deployment_name", body=deployment_body)

    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "test_deployment_guid"


def test_delete_deployment_success(client, mocker: MockFixture):  # noqa: F811
    mock_delete = mocker.patch("httpx.Client.delete")

    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = client.delete_deployment(name="mock_deployment_name")

    assert response["success"] is True
