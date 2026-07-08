import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import Secret, SecretList
from rapyuta_io_sdk_v2.models.secret import SecretCreate
from tests.data.mock_data import (
    secret_body,
    secret_model_mock,
    secretlist_model_mock,
    docker_secret_typed_model_mock,
    opaque_secret_body,
    opaque_secret_model_mock,
)
from tests.utils.fixtures import client


def test_list_secrets_success(client, secretlist_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=secretlist_model_mock,
    )

    # Call the list_secrets method
    response = client.list_secrets()

    # Validate the response
    assert isinstance(response, SecretList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    secret = response.items[0]
    assert secret.metadata.guid == "secret-aaaaaaaaaaaaaaaaaaaa"
    assert secret.metadata.name == "test_secret"
    assert secret.kind == "Secret"
    assert secret.spec.type == "Docker"
    assert secret.spec.docker is not None
    assert secret.spec.docker.username == "testuser"


def test_list_secrets_not_found(client, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        client.list_secrets()

    assert str(exc.value) == "not found"


def test_create_secret_success(
    client, secret_body, secret_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=secret_model_mock,
    )

    # Call the create_secret method
    response = client.create_secret(secret_body)

    # Validate the response
    assert isinstance(response, Secret)
    assert response.metadata.guid == "secret-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test_secret"
    assert response.spec.type == "Docker"


def test_create_secret_already_exists(client, secret_body, mocker: MockFixture):
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "secret already exists"},
    )

    with pytest.raises(Exception) as exc:
        client.create_secret(secret_body)

    assert str(exc.value) == "secret already exists"


def test_update_secret_success(
    client, secret_body, secret_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=secret_model_mock,
    )

    # Call the update_secret method
    response = client.update_secret("secret-aaaaaaaaaaaaaaaaaaaa", body=secret_body)

    # Validate the response
    assert isinstance(response, Secret)
    assert response.metadata.guid == "secret-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test_secret"
    assert response.spec.type == "Docker"


def test_delete_secret_success(client, mocker: MockFixture):
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_secret method
    response = client.delete_secret("secret-aaaaaaaaaaaaaaaaaaaa")

    # Validate the response
    assert response is None


def test_get_secret_success(client, secret_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=secret_model_mock,
    )

    # Call the get_secret method
    response = client.get_secret("secret-aaaaaaaaaaaaaaaaaaaa")

    # Validate the response
    assert isinstance(response, Secret)
    assert response.metadata.guid == "secret-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test_secret"
    assert response.spec.type == "Docker"
    assert response.spec.docker.username == "testuser"
    assert response.spec.secret_keys == ["username", "email", "registry"]


# ── New: type / secretKeys ────────────────────────────────────────────────────


def test_get_docker_secret_with_type_and_keys(
    client, docker_secret_typed_model_mock, mocker: MockFixture
):
    """Server returns a Docker secret with type and secretKeys fields."""
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=docker_secret_typed_model_mock,
    )

    response = client.get_secret("docker_typed_secret")

    assert isinstance(response, Secret)
    assert response.metadata.guid == "secret-bbbbbbbbbbbbbbbbbbbb"
    assert response.spec.type == "Docker"
    assert response.spec.docker is not None
    assert response.spec.docker.registry == "docker.io"
    assert response.spec.docker.username == "testuser"
    # password is write-only — DockerSpec (read model) intentionally omits it
    assert response.spec.secret_keys == ["username", "password", "email", "registry"]


def test_get_opaque_secret_success(
    client, opaque_secret_model_mock, mocker: MockFixture
):
    """Server returns an Opaque secret with data and secretKeys."""
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=opaque_secret_model_mock,
    )

    response = client.get_secret("opaque_test_secret")

    assert isinstance(response, Secret)
    assert response.metadata.guid == "secret-cccccccccccccccccccc"
    assert response.spec.type == "Opaque"
    assert response.spec.data == {"API_KEY": "my-api-key-value", "DB_PASSWORD": "my-db-password"}
    assert set(response.spec.secret_keys) == {"API_KEY", "DB_PASSWORD"}


def test_create_opaque_secret_success(
    client, opaque_secret_body, opaque_secret_model_mock, mocker: MockFixture
):
    """Creating an Opaque secret returns a parsed Secret model."""
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=opaque_secret_model_mock,
    )

    response = client.create_secret(opaque_secret_body)

    assert isinstance(response, Secret)
    assert response.spec.type == "Opaque"
    assert "API_KEY" in response.spec.data


# ── New: SecretCreate model validation ───────────────────────────────────────


def test_secret_create_model_docker_requires_password():
    """SecretCreate raises when creating a Docker secret without a password."""
    with pytest.raises(Exception, match="password"):
        SecretCreate.model_validate(
            {
                "apiVersion": "apiextensions.rapyuta.io/v1",
                "kind": "Secret",
                "metadata": {"name": "bad-docker-secret"},
                "spec": {
                    "type": "Docker",
                    "docker": {
                        "registry": "docker.io",
                        "username": "user",
                        "email": "user@example.com",
                        # password intentionally missing
                    },
                },
            }
        )


def test_secret_create_model_opaque_requires_data():
    """SecretCreate raises when creating an Opaque secret without data."""
    with pytest.raises(Exception, match="data"):
        SecretCreate.model_validate(
            {
                "apiVersion": "apiextensions.rapyuta.io/v1",
                "kind": "Secret",
                "metadata": {"name": "bad-opaque-secret"},
                "spec": {
                    "type": "Opaque",
                    # data intentionally missing
                },
            }
        )


def test_secret_create_model_docker_valid():
    """SecretCreate succeeds with all required Docker fields."""
    secret = SecretCreate.model_validate(
        {
            "apiVersion": "apiextensions.rapyuta.io/v1",
            "kind": "Secret",
            "metadata": {"name": "valid-docker-secret"},
            "spec": {
                "type": "Docker",
                "docker": {
                    "registry": "docker.io",
                    "username": "user",
                    "email": "user@example.com",
                    "password": "supersecret",
                },
            },
        }
    )
    assert secret.spec.docker.password == "supersecret"
    assert secret.spec.type == "Docker"


def test_secret_create_model_opaque_valid():
    """SecretCreate succeeds with all required Opaque fields."""
    secret = SecretCreate.model_validate(
        {
            "apiVersion": "apiextensions.rapyuta.io/v1",
            "kind": "Secret",
            "metadata": {"name": "valid-opaque-secret"},
            "spec": {
                "type": "Opaque",
                "data": {"MY_KEY": "my-value"},
            },
        }
    )
    assert secret.spec.type == "Opaque"
    assert secret.spec.data == {"MY_KEY": "my-value"}


