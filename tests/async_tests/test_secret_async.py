import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import SecretList, Secret
from tests.utils.fixtures import async_client
from tests.data import (
    secret_body,
    secret_model_mock,
    secretlist_model_mock,
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


@pytest.mark.asyncio
async def test_delete_secret_success(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await async_client.delete_secret(name="test_secret")

    assert response is None
