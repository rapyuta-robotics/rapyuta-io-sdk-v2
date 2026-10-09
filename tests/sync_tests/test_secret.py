# Copyright 2026 Rapyuta Robotics
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import pytest

from rapyuta_io_sdk_v2.exceptions import HttpAlreadyExistsError, HttpNotFoundError
from rapyuta_io_sdk_v2.models import (
    Secret,
    SecretCreate,
    SecretList,
)

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import Client


def test_list_secrets_success(
    *, client: Client, secretlist_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
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


def test_list_secrets_not_found(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        client.list_secrets()

    assert str(exc.value) == "not found"


def test_create_secret_success(
    *,
    client: Client,
    secret_body: dict[str, Any],
    secret_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=secret_model_mock,
    )

    # Call the create_secret method
    response = client.create_secret(SecretCreate.model_validate(secret_body))

    # Validate the response
    assert isinstance(response, Secret)
    assert response.metadata.guid == "secret-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test_secret"
    assert response.spec.type == "Docker"


def test_create_secret_already_exists(
    *, client: Client, secret_body: dict[str, Any], mocker: MockFixture
) -> None:
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "secret already exists"},
    )

    with pytest.raises(HttpAlreadyExistsError) as exc:
        client.create_secret(SecretCreate.model_validate(secret_body))

    assert str(exc.value) == "secret already exists"


def test_update_secret_success(
    *,
    client: Client,
    secret_body: dict[str, Any],
    secret_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=secret_model_mock,
    )

    # Call the update_secret method
    response = client.update_secret(
        "secret-aaaaaaaaaaaaaaaaaaaa", body=SecretCreate.model_validate(secret_body)
    )

    # Validate the response
    assert isinstance(response, Secret)
    assert response.metadata.guid == "secret-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test_secret"
    assert response.spec.type == "Docker"


def test_delete_secret_success(*, client: Client, mocker: MockFixture) -> None:
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


def test_get_secret_success(
    *, client: Client, secret_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
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
    *,
    client: Client,
    docker_secret_typed_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
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
    *, client: Client, opaque_secret_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
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
    assert response.spec.data == {
        "API_KEY": "my-api-key-value",
        "DB_PASSWORD": "my-db-password",
    }
    assert set(response.spec.secret_keys) == {"API_KEY", "DB_PASSWORD"}


def test_create_opaque_secret_success(
    *,
    client: Client,
    opaque_secret_body: dict[str, Any],
    opaque_secret_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    """Creating an Opaque secret returns a parsed Secret model."""
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=opaque_secret_model_mock,
    )

    response = client.create_secret(SecretCreate.model_validate(opaque_secret_body))

    assert isinstance(response, Secret)
    assert response.spec.type == "Opaque"
    assert "API_KEY" in response.spec.data


# ── New: SecretCreate model validation ───────────────────────────────────────


def test_secret_create_model_docker_requires_password() -> None:
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


def test_secret_create_model_opaque_requires_data() -> None:
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


def test_secret_create_model_docker_valid() -> None:
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


def test_secret_create_model_opaque_valid() -> None:
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
