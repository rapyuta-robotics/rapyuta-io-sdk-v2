import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import Backup, BackupList
from tests.data import (
    backup_body,
    backup_model_mock,
    backuplist_model_mock,
)
from tests.utils.fixtures import client


def test_list_backups_success(client, backuplist_model_mock, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=backuplist_model_mock,
    )

    response = client.list_backups(database="orders-db")

    assert isinstance(response, BackupList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    backup = response.items[0]
    assert backup.metadata.guid == "backup-mockbackup12345678901"
    assert backup.metadata.name == "orders-nightly"
    assert backup.spec.database == "orders-db"
    assert backup.spec.type == "scheduled"
    assert backup.status.phase == "Ready"
    assert backup.spec.barman_image == "barman:17"


def test_get_backup_success(client, backup_model_mock, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=backup_model_mock,
    )

    response = client.get_backup(name="backup-mockbackup12345678901")

    assert isinstance(response, Backup)
    assert response.metadata.guid == "backup-mockbackup12345678901"
    assert response.spec.schedule == "0 2 * * *"
    assert response.status.latest_run.verification.check == "Passed"


def test_get_backup_not_found(client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "backup not found"},
    )

    with pytest.raises(Exception) as exc:
        client.get_backup(name="notfound")

    assert str(exc.value) == "backup not found"


def test_create_backup_success(
    client, backup_body, backup_model_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=202,
        json=backup_model_mock,
    )

    response = client.create_backup(body=backup_body)

    assert isinstance(response, Backup)
    assert response.metadata.name == "orders-nightly"
    assert response.spec.database == "orders-db"


def test_create_backup_unauthorized(client, backup_body, mocker: MockFixture):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        client.create_backup(body=backup_body)

    assert str(exc.value) == "unauthorized"


def test_delete_backup_success(client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.Client.delete")
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    response = client.delete_backup(name="backup-mockbackup12345678901")

    assert response is None


def test_get_backup_surfaces_file_uploads(client, backup_model_mock, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(status_code=200, json=backup_model_mock)

    backup = client.get_backup(name="orders-nightly")

    # A restore is addressed by file-upload GUID, so dropping these on parse
    # would leave no way to find the archive to restore.
    assert backup.status.step == "archiving base backup"
    assert len(backup.status.file_uploads) == 1
    upload = backup.status.file_uploads[0]
    assert upload.guid == "fileupload-d9upialugeis73e1to40"
    assert upload.role == "base"
    assert upload.backup_id == "20260101T020000"
    assert upload.size_bytes == 104857600
    assert "fileUploads" in backup.model_dump(exclude_none=True, by_alias=True)["status"]
