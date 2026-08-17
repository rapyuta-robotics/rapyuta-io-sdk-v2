import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import Database, DatabaseList
from tests.data import (
    database_body,
    database_model_mock,
    databaselist_model_mock,
)
from tests.utils.fixtures import async_client


@pytest.mark.asyncio
async def test_list_databases_success(
    async_client, databaselist_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=databaselist_model_mock,
    )

    response = await async_client.list_databases(names=["orders-db"])

    assert isinstance(response, DatabaseList)
    assert response.metadata.continue_ == 1
    assert mock_get.call_args.kwargs["url"].endswith("/v2/databases/")
    assert mock_get.call_args.kwargs["params"]["names"] == ["orders-db"]

    db = response.items[0]
    assert db.metadata.name == "orders-db"
    assert db.spec.postgres.standby.primary_host == "10.1.2.3"
    assert len(db.status.postgres.standby) == 2


@pytest.mark.asyncio
async def test_get_database_success(
    async_client, database_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=database_model_mock,
    )

    response = await async_client.get_database(name="orders-db")

    assert isinstance(response, Database)
    assert mock_get.call_args.kwargs["url"].endswith("/v2/databases/orders-db/")

    # Each standby reports its own entry; a degraded one does not mask the other.
    healthy, degraded = response.status.postgres.standby
    assert (healthy.device_name, healthy.phase) == ("edge-node-02", "running")
    assert (degraded.device_name, degraded.phase) == ("edge-node-03", "crashloop")
    assert degraded.state.status == "waiting"


@pytest.mark.asyncio
async def test_get_database_not_found(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "database not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.get_database(name="notfound")

    assert str(exc.value) == "database not found"


@pytest.mark.asyncio
async def test_create_database_success(
    async_client, database_body, database_model_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=202,
        json=database_model_mock,
    )

    response = await async_client.create_database(body=database_body)

    assert isinstance(response, Database)
    assert response.metadata.name == "orders-db"

    # The topology has to reach the wire camelCased, while postgresql.conf
    # parameters stay snake_case — the apiserver reads them verbatim.
    sent = mock_post.call_args.kwargs["json"]["spec"]["postgres"]
    assert sent["standby"]["primaryInterface"] == "eth0"
    assert sent["standby"]["devices"][0]["deviceName"] == "edge-node-02"
    assert sent["parameters"] == {"max_connections": "200", "shared_buffers": "512MB"}


@pytest.mark.asyncio
async def test_create_database_unauthorized(
    async_client, database_body, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.create_database(body=database_body)

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_update_database_success(
    async_client, database_body, database_model_mock, mocker: MockFixture
):
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=202,
        json=database_model_mock,
    )

    response = await async_client.update_database(name="orders-db", body=database_body)

    assert isinstance(response, Database)
    assert mock_put.call_args.kwargs["url"].endswith("/v2/databases/orders-db/")


@pytest.mark.asyncio
async def test_update_with_empty_devices_removes_every_standby(
    async_client, database_body, database_model_mock, mocker: MockFixture
):
    # nil vs empty is load-bearing on the server: an absent standby block keeps
    # the stored topology, a stated-but-empty one removes every standby. The
    # empty list must therefore survive serialization instead of being dropped.
    database_body["spec"]["postgres"]["standby"]["devices"] = []

    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(status_code=202, json=database_model_mock)

    await async_client.update_database(name="orders-db", body=database_body)

    sent = mock_put.call_args.kwargs["json"]["spec"]["postgres"]
    assert sent["standby"]["devices"] == []


@pytest.mark.asyncio
async def test_delete_database_success(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(
        status_code=202,
        json={"success": True},
    )

    response = await async_client.delete_database(name="orders-db")

    assert response is None
    assert mock_delete.call_args.kwargs["url"].endswith("/v2/databases/orders-db/")
