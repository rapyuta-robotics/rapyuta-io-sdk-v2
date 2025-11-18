import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import NetworkList, Network
from tests.utils.fixtures import async_client
from tests.data import (
    network_body,
    network_model_mock,
    networklist_model_mock,
)


@pytest.mark.asyncio
async def test_list_networks_success(
    async_client, networklist_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=networklist_model_mock,
    )

    response = await async_client.list_networks()

    assert isinstance(response, NetworkList)
    assert len(response.items) == 1
    assert response.items[0].metadata.name == "test-network"


@pytest.mark.asyncio
async def test_get_network_success(async_client, network_model_mock, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=network_model_mock,
    )
    response = await async_client.get_network(name="test-network")
    assert isinstance(response, Network)
    assert response.metadata.name == "test-network"


@pytest.mark.asyncio
async def test_get_network_not_found(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "network not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.get_network(name="notfound")

    assert str(exc.value) == "network not found"


@pytest.mark.asyncio
async def test_create_network_unauthorized(
    async_client, network_body, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.create_network(body=network_body)

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_delete_network_success(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await async_client.delete_network(name="test-network")

    assert response is None
