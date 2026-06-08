import httpx
import pytest
from pydantic import ValidationError
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import DeploymentList, Deployment
from rapyuta_io_sdk_v2.models.deployment import EnvArgsSpec
from tests.utils.fixtures import client
from tests.data import (
    deployment_body,
    deploymentlist_model_mock,
    cloud_deployment_model_mock,
    device_deployment_model_mock,
    cloud_deployment_with_service_account_body,
    cloud_deployment_with_service_account_mock,
    cloud_deployment_with_valuefrom_body,
    cloud_deployment_with_valuefrom_mock,
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


def test_create_deployment_success(
    client, deployment_body, device_deployment_model_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=200,
        json=device_deployment_model_mock,
    )

    response = client.create_deployment(body=deployment_body)

    assert isinstance(response, Deployment)
    assert response.metadata.guid == "dep-device-001"
    assert response.spec.runtime == "device"


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


def test_create_deployment_with_service_account(
    client,
    cloud_deployment_with_service_account_body,
    cloud_deployment_with_service_account_mock,
    mocker: MockFixture,
):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=200,
        json=cloud_deployment_with_service_account_mock,
    )

    response = client.create_deployment(body=cloud_deployment_with_service_account_body)

    assert isinstance(response, Deployment)
    assert response.spec.serviceAccount == "my-service-account"
    assert response.spec.runtime == "cloud"
    assert response.metadata.guid == "dep-cloud-002"


# ── New: valueFrom / SecretKeyRef in envArgs ─────────────────────────────────


def test_get_deployment_with_valuefrom_success(
    client, cloud_deployment_with_valuefrom_mock, mocker: MockFixture
):
    """GET a deployment whose envArgs contain valueFrom.secretKeyRef entries."""
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=cloud_deployment_with_valuefrom_mock,
    )

    response = client.get_deployment(name="cloud_deployment_secret_env")

    assert isinstance(response, Deployment)
    assert response.metadata.guid == "dep-cloud-003"
    assert response.spec.runtime == "cloud"

    env_args = response.spec.envArgs
    assert env_args is not None

    plain = next(a for a in env_args if a.name == "PLAIN_VAR")
    assert plain.value == "plain-value"
    assert plain.valueFrom is None

    api_key = next(a for a in env_args if a.name == "API_KEY")
    assert api_key.value is None
    assert api_key.valueFrom is not None
    assert api_key.valueFrom.secret_key_ref is not None
    assert api_key.valueFrom.secret_key_ref.name == "my-api-secret"
    assert api_key.valueFrom.secret_key_ref.key == "API_KEY"
    # server resolves the value and returns it
    assert api_key.valueFrom.secret_key_ref.value == "resolved-api-key"

    db_pass = next(a for a in env_args if a.name == "DB_PASS")
    assert db_pass.exposed is True
    assert db_pass.exposed_name == "DB_PASS"
    assert db_pass.valueFrom.secret_key_ref.name == "db-credentials"


def test_create_deployment_with_valuefrom_success(
    client,
    cloud_deployment_with_valuefrom_body,
    cloud_deployment_with_valuefrom_mock,
    mocker: MockFixture,
):
    """POST a deployment with valueFrom envArgs and verify the response is parsed."""
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=200,
        json=cloud_deployment_with_valuefrom_mock,
    )

    response = client.create_deployment(body=cloud_deployment_with_valuefrom_body)

    assert isinstance(response, Deployment)
    assert response.metadata.guid == "dep-cloud-003"
    api_key = next(a for a in response.spec.envArgs if a.name == "API_KEY")
    assert api_key.valueFrom.secret_key_ref.key == "API_KEY"


# ── New: EnvArgsSpec model validation ────────────────────────────────────────


def test_env_args_spec_valuefrom_model_validation():
    """EnvArgsSpec correctly parses a valueFrom.secretKeyRef payload."""
    arg = EnvArgsSpec.model_validate(
        {
            "name": "MY_SECRET_ARG",
            "valueFrom": {
                "secretKeyRef": {
                    "name": "my-secret",
                    "key": "MY_KEY",
                }
            },
        }
    )
    assert arg.name == "MY_SECRET_ARG"
    assert arg.value is None
    assert arg.valueFrom is not None
    assert arg.valueFrom.secret_key_ref.name == "my-secret"
    assert arg.valueFrom.secret_key_ref.key == "MY_KEY"
    assert arg.valueFrom.secret_key_ref.value is None


def test_env_args_spec_plain_and_valuefrom_coexist():
    """EnvArgsSpec with both value and valueFrom can be parsed (server may allow both)."""
    arg = EnvArgsSpec.model_validate(
        {
            "name": "OVERRIDE_ARG",
            "value": "fallback",
            "valueFrom": {
                "secretKeyRef": {
                    "name": "override-secret",
                    "key": "override-key",
                    "value": "injected",
                }
            },
        }
    )
    assert arg.value == "fallback"
    assert arg.valueFrom.secret_key_ref.value == "injected"


