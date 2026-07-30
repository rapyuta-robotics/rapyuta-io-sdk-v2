# ruff: noqa: F401
"""Model round-trip tests for the standby topology fields on Database.

Standby is a facet of the Database resource (spec.postgres.standby); the
replication user + standby status come back on read. These assert the SDK model
parses a server-shaped (camelCase) payload and survives a dump/reload.
"""

from rapyuta_io_sdk_v2.models import Database
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
