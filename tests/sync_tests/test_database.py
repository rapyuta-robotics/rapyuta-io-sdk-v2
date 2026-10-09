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


"""Database CRUD and standby-topology tests.

Standby is a facet of the Database resource (spec.postgres.standby); the
replication user + standby status come back on read. These assert the SDK model
parses a server-shaped (camelCase) payload, survives a dump/reload, and that the
client sends the right routes and bodies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import Client

from rapyuta_io_sdk_v2.models import Database, DatabaseList
from rapyuta_io_sdk_v2.models.database import StandbySpec, StandbyStatus


def _database_with_standby() -> dict:
    """Server-shaped GET payload for a DB with one standby device."""
    return {
        "apiVersion": "api.rapyuta.io/v2",
        "kind": "Database",
        "metadata": {"name": "db-standby", "guid": "db-aaaaaaaaaaaaaaaaaaaa"},
        "spec": {
            "type": "postgres",
            "postgres": {
                "version": "17",
                "primary": {
                    "deviceName": "primary-dev",
                    "deviceGuid": "dev-primary",
                    "dataDirectory": "/opt/rapyuta/volumes/postgres/db-standby",
                    "port": 5432,
                },
                "standby": {
                    "primaryInterface": "eth0",
                    "primaryHost": "10.1.2.3",
                    "devices": [
                        {
                            "deviceName": "standby-dev",
                            "deviceGuid": "dev-standby",
                            "dataDirectory": "/opt/rapyuta/volumes/postgres/db-standby",
                            "port": 5432,
                        }
                    ],
                },
                "users": {
                    # replication user is server-generated into the managed
                    # secret; refs come back with `value` redacted
                    "replication": {
                        "username": {
                            "name": "db-standby-db-credentials",
                            "key": "replication_username",
                            "value": "",
                        },
                        "password": {
                            "name": "db-standby-db-credentials",
                            "key": "replication_password",
                            "value": "",
                        },
                    },
                },
            },
        },
        "status": {
            "phase": "Running",
            "postgres": {
                "primary": {
                    "deviceName": "primary-dev",
                    "port": 5432,
                    "phase": "running",
                },
                "standby": [
                    {"deviceName": "standby-dev", "port": 5432, "phase": "running"}
                ],
            },
        },
    }


def test_standby_spec_parses_from_server_payload() -> None:
    db = Database.model_validate(_database_with_standby())

    sb = db.spec.postgres.standby
    assert isinstance(sb, StandbySpec)
    assert sb.primary_interface == "eth0"
    assert sb.primary_host == "10.1.2.3"
    assert [d.device_name for d in sb.devices] == ["standby-dev"]

    # server-generated replication user surfaces as secret refs, value redacted
    repl = db.spec.postgres.users.replication
    assert repl.username.key == "replication_username"
    assert repl.password.key == "replication_password"
    assert repl.username.value == ""

    # per-device standby status merged in
    st = db.status.postgres.standby
    assert isinstance(st[0], StandbyStatus)
    assert st[0].device_name == "standby-dev"
    assert st[0].phase == "running"


def test_standby_round_trip_survives_dump_reload() -> None:
    db = Database.model_validate(_database_with_standby())
    reloaded = Database.model_validate(db.model_dump(by_alias=True, exclude_none=True))

    assert reloaded.spec.postgres.standby.primary_host == "10.1.2.3"
    assert reloaded.spec.postgres.standby.devices[0].device_name == "standby-dev"
    assert (
        reloaded.spec.postgres.users.replication.username.key == "replication_username"
    )
    assert reloaded.status.postgres.standby[0].device_name == "standby-dev"


def test_standby_omitted_when_absent() -> None:
    payload = _database_with_standby()
    del payload["spec"]["postgres"]["standby"]
    db = Database.model_validate(payload)
    assert db.spec.postgres.standby is None


def test_list_databases_success(
    *, client: Client, databaselist_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=databaselist_model_mock,
    )

    response = client.list_databases(names=["orders-db"])

    assert isinstance(response, DatabaseList)
    assert response.metadata.continue_ == 1
    assert mock_get.call_args.kwargs["url"].endswith("/v2/databases/")
    assert mock_get.call_args.kwargs["params"]["names"] == ["orders-db"]

    db = response.items[0]
    assert db.metadata.name == "orders-db"
    assert db.spec.postgres.standby.primary_host == "10.1.2.3"
    assert len(db.status.postgres.standby) == 2  # noqa: PLR2004 - fixture value


def test_get_database_success(
    *, client: Client, database_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=database_model_mock,
    )

    response = client.get_database(name="orders-db")

    assert isinstance(response, Database)
    assert mock_get.call_args.kwargs["url"].endswith("/v2/databases/orders-db/")
    assert response.spec.postgres.primary.device_name == "edge-node-01"

    # Each standby reports its own entry; a degraded one does not mask the other.
    healthy, degraded = response.status.postgres.standby
    assert (healthy.device_name, healthy.phase) == ("edge-node-02", "running")
    assert (degraded.device_name, degraded.phase) == ("edge-node-03", "failed")
    assert degraded.state.status == "waiting"
    assert degraded.restart_count == 3  # noqa: PLR2004 - fixture value


def test_get_database_not_found(*, client: Client, mocker: MockFixture) -> None:
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "database not found"},
    )

    with pytest.raises(Exception, match=r".+") as exc:
        client.get_database(name="notfound")

    assert str(exc.value) == "database not found"


def test_create_database_success(
    *,
    client: Client,
    database_body: dict[str, Any],
    database_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=202,
        json=database_model_mock,
    )

    response = client.create_database(body=database_body)

    assert isinstance(response, Database)
    assert response.metadata.name == "orders-db"

    # The topology has to reach the wire camelCased, while postgresql.conf
    # parameters stay snake_case — the apiserver reads them verbatim.
    sent = mock_post.call_args.kwargs["json"]["spec"]["postgres"]
    assert sent["standby"]["primaryInterface"] == "eth0"
    assert sent["standby"]["devices"][0]["deviceName"] == "edge-node-02"
    assert sent["standby"]["devices"][0]["dataDirectory"] == (
        "/opt/rapyuta/volumes/orders-db"
    )
    assert sent["parameters"] == {"max_connections": "200", "shared_buffers": "512MB"}


def test_create_database_unauthorized(
    *, client: Client, database_body: dict[str, Any], mocker: MockFixture
) -> None:
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception, match=r".+") as exc:
        client.create_database(body=database_body)

    assert str(exc.value) == "unauthorized"


def test_update_database_success(
    *,
    client: Client,
    database_body: dict[str, Any],
    database_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(
        status_code=202,
        json=database_model_mock,
    )

    response = client.update_database(name="orders-db", body=database_body)

    assert isinstance(response, Database)
    assert mock_put.call_args.kwargs["url"].endswith("/v2/databases/orders-db/")


def test_update_with_empty_devices_removes_every_standby(
    *,
    client: Client,
    database_body: dict[str, Any],
    database_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    # nil vs empty is load-bearing on the server: an absent standby block keeps
    # the stored topology, a stated-but-empty one removes every standby. The
    # empty list must therefore survive serialization instead of being dropped.
    database_body["spec"]["postgres"]["standby"]["devices"] = []

    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(status_code=202, json=database_model_mock)

    client.update_database(name="orders-db", body=database_body)

    sent = mock_put.call_args.kwargs["json"]["spec"]["postgres"]
    assert sent["standby"]["devices"] == []


def test_delete_database_success(*, client: Client, mocker: MockFixture) -> None:
    mock_delete = mocker.patch("httpx.Client.delete")
    mock_delete.return_value = httpx.Response(
        status_code=202,
        json={"success": True},
    )

    response = client.delete_database(name="orders-db")

    assert response is None
    assert mock_delete.call_args.kwargs["url"].endswith("/v2/databases/orders-db/")
    assert mock_delete.call_args.kwargs["params"] is None


def test_delete_database_force(*, client: Client, mocker: MockFixture) -> None:
    mock_delete = mocker.patch("httpx.Client.delete")
    mock_delete.return_value = httpx.Response(status_code=204)

    client.delete_database(name="orders-db", force=True)

    assert mock_delete.call_args.kwargs["url"].endswith("/v2/databases/orders-db/")
    assert mock_delete.call_args.kwargs["params"] == {"force": "true"}
