import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import SecretList, Secret
from rapyuta_io_sdk_v2.models.secret import SecretCreate
from tests.utils.fixtures import async_client
from tests.data import (
    secret_body,
    secret_model_mock,
    secretlist_model_mock,
    docker_secret_typed_model_mock,
    opaque_secret_body,
    opaque_secret_model_mock,
)


@pytest.mark.asyncio
async def test_list_secrets_success(
    async_client, secretlist_model_mock, mocker: MockFixture
):
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
async def test_get_secret_success(async_client, secret_model_mock, mocker: MockFixture):
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
async def test_get_secret_not_found(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "secret not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.get_secret(name="notfound")

    assert str(exc.value) == "secret not found"


@pytest.mark.asyncio
async def test_create_secret_unauthorized(async_client, secret_body, mocker: MockFixture):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.create_secret(body=secret_body)

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_update_secret_success(
    async_client, secret_body, secret_model_mock, mocker: MockFixture
):
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=secret_model_mock,
    )

    response = await async_client.update_secret(name="test_secret", body=secret_body)

    assert isinstance(response, Secret)
    assert response.metadata.name == "test_secret"
    assert response.spec.type == "Docker"


@pytest.mark.asyncio
async def test_delete_secret_success(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await async_client.delete_secret(name="test_secret")

    assert response is None


# ── New: type / secretKeys ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_docker_secret_with_type_and_keys(
    async_client, docker_secret_typed_model_mock, mocker: MockFixture
):
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
    async_client, opaque_secret_model_mock, mocker: MockFixture
):
    """Server returns an Opaque secret with data and secretKeys."""
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=opaque_secret_model_mock,
    )

    response = await async_client.get_secret(name="opaque_test_secret")

    assert isinstance(response, Secret)
    assert response.spec.type == "Opaque"
    assert response.spec.data == {"API_KEY": "my-api-key-value", "DB_PASSWORD": "my-db-password"}
    assert set(response.spec.secret_keys) == {"API_KEY", "DB_PASSWORD"}


@pytest.mark.asyncio
async def test_create_opaque_secret_success(
    async_client, opaque_secret_body, opaque_secret_model_mock, mocker: MockFixture
):
    """Creating an Opaque secret returns a parsed Secret model."""
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=opaque_secret_model_mock,
    )

    response = await async_client.create_secret(body=opaque_secret_body)

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
                "spec": {"type": "Opaque"},
            }
        )


