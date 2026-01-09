import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import StaticRouteList, StaticRoute
from tests.utils.fixtures import async_client
from tests.data import (
    staticroute_body,
    staticroute_model_mock,
    staticroutelist_model_mock,
)


@pytest.mark.asyncio
async def test_list_staticroutes_success(
    async_client, staticroutelist_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=staticroutelist_model_mock,
    )

    response = await async_client.list_staticroutes()

    assert isinstance(response, StaticRouteList)
    assert len(response.items) == 1
    assert response.items[0].metadata.name == "test-staticroute"


@pytest.mark.asyncio
async def test_get_staticroute_success(
    async_client, staticroute_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=staticroute_model_mock,
    )
    response = await async_client.get_staticroute(name="test-staticroute")
    assert isinstance(response, StaticRoute)
    assert response.metadata.name == "test-staticroute"


@pytest.mark.asyncio
async def test_get_staticroute_not_found(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "staticroute not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.get_staticroute(name="notfound")

    assert str(exc.value) == "staticroute not found"


@pytest.mark.asyncio
async def test_create_staticroute_unauthorized(
    async_client, staticroute_body, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.create_staticroute(body=staticroute_body)

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_update_staticroute_success(
    async_client, staticroute_body, staticroute_model_mock, mocker: MockFixture
):
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=staticroute_model_mock,
    )

    response = await async_client.update_staticroute(
        name="test-staticroute", body=staticroute_body
    )

    assert isinstance(response, StaticRoute)
    assert response.metadata.name == "test-staticroute"


@pytest.mark.asyncio
async def test_delete_staticroute_success(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await async_client.delete_staticroute(name="test-staticroute")

    assert response is None
