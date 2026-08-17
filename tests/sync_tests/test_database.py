# ruff: noqa: F811, F401
"""Database CRUD and standby-topology tests.

Standby is a facet of the Database resource (spec.postgres.standby); the
replication user + standby status come back on read. These assert the SDK model
parses a server-shaped (camelCase) payload, survives a dump/reload, and that the
client sends the right routes and bodies.
"""

import httpx
import pytest
from pytest_mock import MockFixture

from rapyuta_io_sdk_v2.models import Database, DatabaseList
from rapyuta_io_sdk_v2.models.database import StandbySpec, StandbyStatus
from tests.data import (
    database_body,
    database_model_mock,
    databaselist_model_mock,
)
from tests.utils.fixtures import client


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


def test_standby_spec_parses_from_server_payload():
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


def test_standby_round_trip_survives_dump_reload():
    db = Database.model_validate(_database_with_standby())
    reloaded = Database.model_validate(db.model_dump(by_alias=True, exclude_none=True))

    assert reloaded.spec.postgres.standby.primary_host == "10.1.2.3"
    assert reloaded.spec.postgres.standby.devices[0].device_name == "standby-dev"
    assert reloaded.spec.postgres.users.replication.username.key == "replication_username"
    assert reloaded.status.postgres.standby[0].device_name == "standby-dev"


def test_standby_omitted_when_absent():
    payload = _database_with_standby()
    del payload["spec"]["postgres"]["standby"]
    db = Database.model_validate(payload)
    assert db.spec.postgres.standby is None


def test_list_databases_success(client, databaselist_model_mock, mocker: MockFixture):
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
    assert len(db.status.postgres.standby) == 2


def test_get_database_success(client, database_model_mock, mocker: MockFixture):
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
    assert (degraded.device_name, degraded.phase) == ("edge-node-03", "crashloop")
    assert degraded.state.status == "waiting"
    assert degraded.restart_count == 3


def test_get_database_not_found(client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "database not found"},
    )

    with pytest.raises(Exception) as exc:
        client.get_database(name="notfound")

    assert str(exc.value) == "database not found"


def test_create_database_success(
    client, database_body, database_model_mock, mocker: MockFixture
):
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


def test_create_database_unauthorized(client, database_body, mocker: MockFixture):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        client.create_database(body=database_body)

    assert str(exc.value) == "unauthorized"


def test_update_database_success(
    client, database_body, database_model_mock, mocker: MockFixture
):
    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(
        status_code=202,
        json=database_model_mock,
    )

    response = client.update_database(name="orders-db", body=database_body)

    assert isinstance(response, Database)
    assert mock_put.call_args.kwargs["url"].endswith("/v2/databases/orders-db/")


def test_update_with_empty_devices_removes_every_standby(
    client, database_body, database_model_mock, mocker: MockFixture
):
    # nil vs empty is load-bearing on the server: an absent standby block keeps
    # the stored topology, a stated-but-empty one removes every standby. The
    # empty list must therefore survive serialization instead of being dropped.
    database_body["spec"]["postgres"]["standby"]["devices"] = []

    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(status_code=202, json=database_model_mock)

    client.update_database(name="orders-db", body=database_body)

    sent = mock_put.call_args.kwargs["json"]["spec"]["postgres"]
    assert sent["standby"]["devices"] == []


def test_delete_database_success(client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.Client.delete")
    mock_delete.return_value = httpx.Response(
        status_code=202,
        json={"success": True},
    )

    response = client.delete_database(name="orders-db")

    assert response is None
    assert mock_delete.call_args.kwargs["url"].endswith("/v2/databases/orders-db/")
