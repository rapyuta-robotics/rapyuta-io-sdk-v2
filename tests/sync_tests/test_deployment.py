import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import DeploymentList, Deployment
from tests.utils.fixtures import client
from tests.data import (
    deployment_body,
    deploymentlist_model_mock,
    cloud_deployment_model_mock,
    device_deployment_model_mock,
)


def test_list_deployments_success(client, deploymentlist_model_mock, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")
    # Use the DeploymentList pydantic model mock and dump as JSON
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=deploymentlist_model_mock,
    )

    response = client.list_deployments()

    assert isinstance(response, DeploymentList)
    assert response.metadata.continue_ == 123
    assert len(response.items) == 2
    cloud_dep = response.items[0]
    device_dep = response.items[1]
    assert cloud_dep.spec.runtime == "cloud"
    assert device_dep.spec.runtime == "device"
    assert cloud_dep.metadata.guid == "dep-cloud-001"
    assert device_dep.metadata.guid == "dep-device-001"


def test_list_deployments_not_found(client, mocker: MockFixture):
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


def test_get_cloud_deployment_success(
    client, cloud_deployment_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=cloud_deployment_model_mock,
    )
    response = client.get_deployment(name="cloud_deployment_sample")
    assert isinstance(response, Deployment)
    assert response.spec.runtime == "cloud"
    assert response.metadata.guid == "dep-cloud-001"


def test_get_device_deployment_success(
    client, device_deployment_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=device_deployment_model_mock,
    )
    response = client.get_deployment(name="device_deployment_sample")
    assert isinstance(response, Deployment)
    assert response.spec.runtime == "device"
    assert response.metadata.guid == "dep-device-001"


def test_get_deployment_not_found(client, mocker: MockFixture):
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


def test_create_deployment_unauthorized(client, deployment_body, mocker: MockFixture):
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        client.create_deployment(body=deployment_body)

    assert str(exc.value) == "unauthorized"


def test_create_deployment_unauthorized(client, deployment_body, mocker: MockFixture):
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        client.create_deployment(body=deployment_body)

    assert str(exc.value) == "unauthorized"


def test_update_deployment_success(
    client, deployment_body, device_deployment_model_mock, mocker: MockFixture
):
    mock_put = mocker.patch("httpx.Client.patch")

    mock_put.return_value = httpx.Response(
        status_code=200,
        json=device_deployment_model_mock,
    )

    response = client.update_deployment(body=deployment_body)

    assert isinstance(response, Deployment)
    assert response.metadata.guid == "dep-device-001"


def test_delete_deployment_success(client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.Client.delete")

    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = client.delete_deployment(name="mock_deployment_name")

    assert response is None
