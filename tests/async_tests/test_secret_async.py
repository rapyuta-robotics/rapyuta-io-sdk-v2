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

from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError, UnauthorizedAccessError
from rapyuta_io_sdk_v2.models import (
    Secret,
    SecretCreate,
    SecretList,
)

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import AsyncClient


@pytest.mark.asyncio
async def test_list_secrets_success(
    *,
    async_client: AsyncClient,
    secretlist_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=secretlist_model_mock,
    )

    response = await async_client.list_secrets()

    assert isinstance(response, SecretList)
    assert len(response.items) == 1
    assert response.items[0].metadata.name == "test_secret"
    assert response.items[0].spec.type == "Docker"


@pytest.mark.asyncio
async def test_get_secret_success(
    *, async_client: AsyncClient, secret_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=secret_model_mock,
    )
    response = await async_client.get_secret(name="test_secret")
    assert isinstance(response, Secret)
    assert response.metadata.name == "test_secret"
    assert response.spec.type == "Docker"
    assert response.spec.docker.username == "testuser"
    assert response.spec.secret_keys == ["username", "email", "registry"]


@pytest.mark.asyncio
async def test_get_secret_not_found(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "secret not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        await async_client.get_secret(name="notfound")

    assert str(exc.value) == "secret not found"


@pytest.mark.asyncio
async def test_create_secret_unauthorized(
    *, async_client: AsyncClient, secret_body: dict[str, Any], mocker: MockFixture
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        await async_client.create_secret(body=SecretCreate.model_validate(secret_body))

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_update_secret_success(
    *,
    async_client: AsyncClient,
    secret_body: dict[str, Any],
    secret_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=secret_model_mock,
    )

    response = await async_client.update_secret(
        name="test_secret", body=SecretCreate.model_validate(secret_body)
    )

    assert isinstance(response, Secret)
    assert response.metadata.name == "test_secret"
    assert response.spec.type == "Docker"


@pytest.mark.asyncio
async def test_delete_secret_success(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await async_client.delete_secret(name="test_secret")

    assert response is None


# ── New: type / secretKeys ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_docker_secret_with_type_and_keys(
    *,
    async_client: AsyncClient,
    docker_secret_typed_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    """Server returns a Docker secret with type and secretKeys fields."""
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=docker_secret_typed_model_mock,
    )

    response = await async_client.get_secret(name="docker_typed_secret")

    assert isinstance(response, Secret)
    assert response.spec.type == "Docker"
    assert response.spec.docker.registry == "docker.io"
    assert response.spec.docker.username == "testuser"
    # password is write-only — DockerSpec (read model) intentionally omits it
    assert response.spec.secret_keys == ["username", "password", "email", "registry"]


@pytest.mark.asyncio
async def test_get_opaque_secret_success(
    *,
    async_client: AsyncClient,
    opaque_secret_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    """Server returns an Opaque secret with data and secretKeys."""
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=opaque_secret_model_mock,
    )

    response = await async_client.get_secret(name="opaque_test_secret")

    assert isinstance(response, Secret)
    assert response.spec.type == "Opaque"
    assert response.spec.data == {
        "API_KEY": "my-api-key-value",
        "DB_PASSWORD": "my-db-password",
    }
    assert set(response.spec.secret_keys) == {"API_KEY", "DB_PASSWORD"}


@pytest.mark.asyncio
async def test_create_opaque_secret_success(
    *,
    async_client: AsyncClient,
    opaque_secret_body: dict[str, Any],
    opaque_secret_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    """Creating an Opaque secret returns a parsed Secret model."""
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=opaque_secret_model_mock,
    )

    response = await async_client.create_secret(
        body=SecretCreate.model_validate(opaque_secret_body)
    )

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
                "spec": {"type": "Opaque"},
            }
        )
