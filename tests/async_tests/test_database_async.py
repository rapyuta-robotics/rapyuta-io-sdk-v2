import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import Database, DatabaseList, Backup, BackupList
from tests.data.mock_data import (
    database_body,
    database_model_mock,
    databaselist_model_mock,
    database_patch_body,
    backup_model_mock,
    backuplist_model_mock,
)
from tests.utils.fixtures import async_client


MOCK_DATABASE_NAME = "test-postgres-db"
MOCK_BACKUP_ID = "backup-20260127-100000"


# -------------------- DATABASE TESTS --------------------


@pytest.mark.asyncio
async def test_list_databases_success(
    async_client, databaselist_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=databaselist_model_mock,
    )

    response = await async_client.list_databases()

    assert isinstance(response, DatabaseList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    database = response.items[0]
    assert database.metadata.name == MOCK_DATABASE_NAME
    assert database.kind == "Database"
    assert database.spec.type == "postgres"
    assert database.spec.postgres.version == "16"


@pytest.mark.asyncio
async def test_list_databases_with_pagination(
    async_client, databaselist_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=databaselist_model_mock,
    )

    response = await async_client.list_databases(cont=10, limit=25)

    assert isinstance(response, DatabaseList)
    # Verify pagination params were passed
    call_kwargs = mock_get.call_args
    assert call_kwargs.kwargs["params"]["continue"] == 10
    assert call_kwargs.kwargs["params"]["limit"] == 25


@pytest.mark.asyncio
async def test_list_databases_not_found(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.list_databases()

    assert str(exc.value) == "not found"


@pytest.mark.asyncio
async def test_get_database_success(
    async_client, database_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=database_model_mock,
    )

    response = await async_client.get_database(name=MOCK_DATABASE_NAME)

    assert isinstance(response, Database)
    assert response.metadata.name == MOCK_DATABASE_NAME
    assert response.spec.type == "postgres"
    assert response.spec.postgres.version == "16"
    assert response.spec.postgres.primary.deviceName == "test-device-001"
    assert response.status.phase == "running"
    assert response.status.postgres.primary.port == 5432


@pytest.mark.asyncio
async def test_get_database_not_found(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "database not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.get_database(name=MOCK_DATABASE_NAME)

    assert str(exc.value) == "database not found"


@pytest.mark.asyncio
async def test_create_database_success(
    async_client, database_body, database_model_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")

    mock_post.return_value = httpx.Response(
        status_code=201,
        json=database_model_mock,
    )

    response = await async_client.create_database(
        body=database_body,
        project_guid="project-aaaaaaaaaaaaaaaaaaaa",
    )

    assert isinstance(response, Database)
    assert response.metadata.name == MOCK_DATABASE_NAME
    assert response.spec.type == "postgres"
    assert response.spec.postgres.version == "16"


@pytest.mark.asyncio
async def test_create_database_with_dict(
    async_client, database_model_mock, mocker: MockFixture
):
    """Test create_database with dict input instead of model."""
    mock_post = mocker.patch("httpx.AsyncClient.post")

    mock_post.return_value = httpx.Response(
        status_code=201,
        json=database_model_mock,
    )

    body_dict = {
        "apiVersion": "api.rapyuta.io/v2",
        "kind": "Database",
        "metadata": {
            "name": "test-postgres-db",
            "labels": {"app": "postgres"},
        },
        "spec": {
            "type": "postgres",
            "postgres": {
                "version": "16",
                "primary": {
                    "deviceName": "test-device-001",
                },
                "credentials": {
                    "username": "postgres",
                    "password": "password",
                },
            },
        },
    }

    response = await async_client.create_database(body=body_dict)

    assert isinstance(response, Database)
    assert response.metadata.name == MOCK_DATABASE_NAME


@pytest.mark.asyncio
async def test_create_database_conflict(
    async_client, database_body, mocker: MockFixture
):
    """Test create_database when database already exists (409 Conflict)."""
    mock_post = mocker.patch("httpx.AsyncClient.post")

    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "database already exists"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.create_database(body=database_body)

    assert str(exc.value) == "database already exists"


@pytest.mark.asyncio
async def test_update_database_success(
    async_client, database_patch_body, database_model_mock, mocker: MockFixture
):
    mock_put = mocker.patch("httpx.AsyncClient.put")

    # Update the mock to reflect the changes
    updated_mock = database_model_mock.copy()
    updated_mock["spec"]["postgres"]["parameters"] = {
        "max_connections": "200",
        "shared_buffers": "512MB",
    }

    mock_put.return_value = httpx.Response(
        status_code=200,
        json=updated_mock,
    )

    response = await async_client.update_database(
        name=MOCK_DATABASE_NAME,
        body=database_patch_body,
    )

    assert isinstance(response, Database)
    assert response.metadata.name == MOCK_DATABASE_NAME
    assert response.spec.postgres.parameters["max_connections"] == "200"
    assert response.spec.postgres.parameters["shared_buffers"] == "512MB"


@pytest.mark.asyncio
async def test_update_database_with_dict(
    async_client, database_model_mock, mocker: MockFixture
):
    """Test update_database with dict input instead of model."""
    mock_put = mocker.patch("httpx.AsyncClient.put")

    mock_put.return_value = httpx.Response(
        status_code=200,
        json=database_model_mock,
    )

    body_dict = {
        "spec": {
            "type": "postgres",
            "postgres": {
                "version": "16",
                "primary": {
                    "deviceName": "test-device-001",
                },
                "parameters": {
                    "max_connections": "150",
                },
            },
        }
    }

    response = await async_client.update_database(
        name=MOCK_DATABASE_NAME, body=body_dict
    )

    assert isinstance(response, Database)
    assert response.metadata.name == MOCK_DATABASE_NAME


@pytest.mark.asyncio
async def test_update_database_not_found(
    async_client, database_patch_body, mocker: MockFixture
):
    mock_put = mocker.patch("httpx.AsyncClient.put")

    mock_put.return_value = httpx.Response(
        status_code=404,
        json={"error": "database not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.update_database(
            name=MOCK_DATABASE_NAME, body=database_patch_body
        )

    assert str(exc.value) == "database not found"


@pytest.mark.asyncio
async def test_delete_database_success(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    response = await async_client.delete_database(name=MOCK_DATABASE_NAME)

    assert response is None


@pytest.mark.asyncio
async def test_delete_database_not_found(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    mock_delete.return_value = httpx.Response(
        status_code=404,
        json={"error": "database not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.delete_database(name=MOCK_DATABASE_NAME)

    assert str(exc.value) == "database not found"


@pytest.mark.asyncio
async def test_list_database_versions_success(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=["14", "15", "16"],
    )

    response = await async_client.list_database_versions()

    assert isinstance(response, list)
    assert len(response) == 3
    assert "16" in response
    assert "15" in response
    assert "14" in response


# -------------------- BACKUP TESTS --------------------


@pytest.mark.asyncio
async def test_list_backups_success(
    async_client, backuplist_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=backuplist_model_mock,
    )

    response = await async_client.list_backups(database_name=MOCK_DATABASE_NAME)

    assert isinstance(response, BackupList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    backup = response.items[0]
    assert backup.spec.id == MOCK_BACKUP_ID
    assert backup.spec.databaseName == MOCK_DATABASE_NAME
    assert backup.spec.status == "COMPLETED"


@pytest.mark.asyncio
async def test_list_backups_with_pagination(
    async_client, backuplist_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=backuplist_model_mock,
    )

    response = await async_client.list_backups(
        database_name=MOCK_DATABASE_NAME, cont=5, limit=20
    )

    assert isinstance(response, BackupList)
    # Verify pagination params were passed
    call_kwargs = mock_get.call_args
    assert call_kwargs.kwargs["params"]["continue"] == 5
    assert call_kwargs.kwargs["params"]["limit"] == 20


@pytest.mark.asyncio
async def test_list_backups_not_found(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "database not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.list_backups(database_name=MOCK_DATABASE_NAME)

    assert str(exc.value) == "database not found"


@pytest.mark.asyncio
async def test_get_backup_success(
    async_client, backup_model_mock, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=backup_model_mock,
    )

    response = await async_client.get_backup(
        database_name=MOCK_DATABASE_NAME,
        backup_id=MOCK_BACKUP_ID,
    )

    assert isinstance(response, Backup)
    assert response.spec.id == MOCK_BACKUP_ID
    assert response.spec.databaseName == MOCK_DATABASE_NAME
    assert response.spec.status == "COMPLETED"


@pytest.mark.asyncio
async def test_get_backup_not_found(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "backup not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.get_backup(
            database_name=MOCK_DATABASE_NAME, backup_id=MOCK_BACKUP_ID
        )

    assert str(exc.value) == "backup not found"


@pytest.mark.asyncio
async def test_delete_backup_success(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    response = await async_client.delete_backup(
        database_name=MOCK_DATABASE_NAME,
        backup_id=MOCK_BACKUP_ID,
    )

    assert response is None


@pytest.mark.asyncio
async def test_delete_backup_not_found(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    mock_delete.return_value = httpx.Response(
        status_code=404,
        json={"error": "backup not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.delete_backup(
            database_name=MOCK_DATABASE_NAME, backup_id=MOCK_BACKUP_ID
        )

    assert str(exc.value) == "backup not found"


@pytest.mark.asyncio
async def test_restore_backup_success(async_client, mocker: MockFixture):
    mock_post = mocker.patch("httpx.AsyncClient.post")

    mock_post.return_value = httpx.Response(
        status_code=202,
    )

    response = await async_client.restore_backup(
        database_name=MOCK_DATABASE_NAME,
        backup_id=MOCK_BACKUP_ID,
    )

    assert response is None


@pytest.mark.asyncio
async def test_restore_backup_not_found(async_client, mocker: MockFixture):
    mock_post = mocker.patch("httpx.AsyncClient.post")

    mock_post.return_value = httpx.Response(
        status_code=404,
        json={"error": "backup not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.restore_backup(
            database_name=MOCK_DATABASE_NAME, backup_id=MOCK_BACKUP_ID
        )

    assert str(exc.value) == "backup not found"


@pytest.mark.asyncio
async def test_restore_backup_conflict(async_client, mocker: MockFixture):
    """Test restore_backup when database is in invalid state."""
    mock_post = mocker.patch("httpx.AsyncClient.post")

    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "database is not in stopped state"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.restore_backup(
            database_name=MOCK_DATABASE_NAME, backup_id=MOCK_BACKUP_ID
        )

    assert "not in stopped state" in str(exc.value)


@pytest.mark.asyncio
async def test_database_with_standby_and_backup(
    async_client, database_model_mock, mocker: MockFixture
):
    """Test database with standby replication and backup configuration."""
    mock_get = mocker.patch("httpx.AsyncClient.get")

    enhanced_mock = database_model_mock.copy()
    enhanced_mock["spec"]["postgres"]["standby"] = {
        "primaryInterface": "eth0",
        "primaryIP": "192.168.1.100",
        "devices": [
            {
                "deviceName": "standby-device-001",
                "deviceGUID": "device-standby123456789",
                "dataDirectory": "/var/lib/postgresql/standby",
            }
        ],
    }
    enhanced_mock["spec"]["postgres"]["backup"] = {
        "enabled": True,
        "schedule": "0 2 * * *",
        "directory": "/backups",
    }
    enhanced_mock["status"]["postgres"]["standby"] = {
        "phase": "running",
        "replicationLagSeconds": 5,
    }
    enhanced_mock["status"]["postgres"]["backup"] = {
        "lastStatus": "Success",
        "lastBackupTime": "2026-01-27T02:00:00Z",
    }

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=enhanced_mock,
    )

    response = await async_client.get_database(name=MOCK_DATABASE_NAME)

    assert isinstance(response, Database)
    assert response.spec.postgres.standby is not None
    assert response.spec.postgres.standby.primaryIP == "192.168.1.100"
    assert len(response.spec.postgres.standby.devices) == 1
    assert response.spec.postgres.backup.enabled is True
    assert response.status.postgres.standby.replicationLagSeconds == 5
    assert response.status.postgres.backup.lastStatus == "Success"


@pytest.mark.asyncio
async def test_database_with_migration(
    async_client, database_model_mock, mocker: MockFixture
):
    """Test database with migration configuration."""
    mock_get = mocker.patch("httpx.AsyncClient.get")

    migration_mock = database_model_mock.copy()
    migration_mock["spec"]["postgres"]["migration"] = {
        "enabled": True,
        "sourceDataDirectory": "/var/lib/postgresql/old",
    }
    migration_mock["status"]["postgres"]["migration"] = {
        "phase": "running",
        "sourceVersion": "14",
        "startedAt": "2026-01-27T09:00:00Z",
    }

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=migration_mock,
    )

    response = await async_client.get_database(name=MOCK_DATABASE_NAME)

    assert isinstance(response, Database)
    assert response.spec.postgres.migration.enabled is True
    assert (
        response.spec.postgres.migration.sourceDataDirectory
        == "/var/lib/postgresql/old"
    )
    assert response.status.postgres.migration.phase == "running"
    assert response.status.postgres.migration.sourceVersion == "14"
