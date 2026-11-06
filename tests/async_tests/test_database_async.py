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

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import AsyncClient

from rapyuta_io_sdk_v2.models import Database, DatabaseList


@pytest.mark.asyncio
async def test_list_databases_success(
    *,
    async_client: AsyncClient,
    databaselist_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
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
    assert len(db.status.postgres.standby) == 2  # noqa: PLR2004 - fixture value


@pytest.mark.asyncio
async def test_get_database_success(
    *,
    async_client: AsyncClient,
    database_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
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
    assert (degraded.device_name, degraded.phase) == ("edge-node-03", "failed")
    assert degraded.state.status == "waiting"


@pytest.mark.asyncio
async def test_get_database_not_found(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "database not found"},
    )

    with pytest.raises(Exception, match=r".+") as exc:
        await async_client.get_database(name="notfound")

    assert str(exc.value) == "database not found"


@pytest.mark.asyncio
async def test_create_database_success(
    *,
    async_client: AsyncClient,
    database_body: dict[str, Any],
    database_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=202,
        json=database_model_mock,
    )

    response = await async_client.create_database(
        body=Database.model_validate(database_body)
    )

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
    *, async_client: AsyncClient, database_body: dict[str, Any], mocker: MockFixture
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception, match=r".+") as exc:
        await async_client.create_database(body=Database.model_validate(database_body))

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_update_database_success(
    *,
    async_client: AsyncClient,
    database_body: dict[str, Any],
    database_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=202,
        json=database_model_mock,
    )

    response = await async_client.update_database(
        name="orders-db", body=Database.model_validate(database_body)
    )

    assert isinstance(response, Database)
    assert mock_put.call_args.kwargs["url"].endswith("/v2/databases/orders-db/")


@pytest.mark.asyncio
async def test_update_with_empty_devices_removes_every_standby(
    *,
    async_client: AsyncClient,
    database_body: dict[str, Any],
    database_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    # nil vs empty is load-bearing on the server: an absent standby block keeps
    # the stored topology, a stated-but-empty one removes every standby. The
    # empty list must therefore survive serialization instead of being dropped.
    database_body["spec"]["postgres"]["standby"]["devices"] = []

    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(status_code=202, json=database_model_mock)

    await async_client.update_database(
        name="orders-db", body=Database.model_validate(database_body)
    )

    sent = mock_put.call_args.kwargs["json"]["spec"]["postgres"]
    assert sent["standby"]["devices"] == []


@pytest.mark.asyncio
async def test_delete_database_success(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(
        status_code=202,
        json={"success": True},
    )

    response = await async_client.delete_database(name="orders-db")

    assert response is None
    assert mock_delete.call_args.kwargs["url"].endswith("/v2/databases/orders-db/")
    assert mock_delete.call_args.kwargs["params"] is None


@pytest.mark.asyncio
async def test_delete_database_force(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204)

    await async_client.delete_database(name="orders-db", force=True)

    assert mock_delete.call_args.kwargs["url"].endswith("/v2/databases/orders-db/")
    assert mock_delete.call_args.kwargs["params"] == {"force": "true"}
