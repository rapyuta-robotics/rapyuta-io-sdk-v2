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

    from rapyuta_io_sdk_v2 import Client

import copy

from rapyuta_io_sdk_v2.models import Backup, BackupList


def test_list_backups_success(
    *, client: Client, backuplist_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
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


def test_get_backup_success(
    *, client: Client, backup_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
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


def test_get_backup_not_found(*, client: Client, mocker: MockFixture) -> None:
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "backup not found"},
    )

    with pytest.raises(Exception, match=r".+") as exc:
        client.get_backup(name="notfound")

    assert str(exc.value) == "backup not found"


def test_create_backup_success(
    *,
    client: Client,
    backup_body: dict[str, Any],
    backup_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=202,
        json=backup_model_mock,
    )

    response = client.create_backup(body=backup_body)

    assert isinstance(response, Backup)
    assert response.metadata.name == "orders-nightly"
    assert response.spec.database == "orders-db"


def test_create_backup_unauthorized(
    *, client: Client, backup_body: dict[str, Any], mocker: MockFixture
) -> None:
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception, match=r".+") as exc:
        client.create_backup(body=backup_body)

    assert str(exc.value) == "unauthorized"


def test_delete_backup_success(*, client: Client, mocker: MockFixture) -> None:
    mock_delete = mocker.patch("httpx.Client.delete")
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    response = client.delete_backup(name="backup-mockbackup12345678901")

    assert response is None


def test_get_backup_surfaces_the_current_step(
    *, client: Client, backup_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(status_code=200, json=backup_model_mock)

    backup = client.get_backup(name="orders-nightly")

    # The recover dominates a run's duration, so the phase alone cannot tell a
    # slow backup from a stuck one.
    assert backup.status.step == "Uploading"
    assert backup.status.phase == "Ready"


def test_get_ondemand_backup_succeeded(
    *, client: Client, backup_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    body = copy.deepcopy(backup_model_mock)
    body["spec"]["type"] = "onDemand"
    body["spec"].pop("schedule", None)
    body["status"]["phase"] = "Succeeded"

    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(status_code=200, json=body)

    response = client.get_backup(name="backup-mockbackup12345678901")

    assert response.spec.type == "onDemand"
    assert response.status.phase == "Succeeded"


def test_get_backup_keeps_recover_and_database_guid(
    *, client: Client, backup_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    body = copy.deepcopy(backup_model_mock)
    body["spec"]["databaseGuid"] = "database-mock"
    body["status"]["latestRun"]["verification"]["recover"] = "Failed"

    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(status_code=200, json=body)

    response = client.get_backup(name="backup-mockbackup12345678901")
    dumped = response.model_dump(by_alias=True, exclude_none=True)

    assert response.spec.database_guid == "database-mock"
    assert response.status.latest_run.verification.recover == "Failed"
    assert dumped["status"]["latestRun"]["verification"]["recover"] == "Failed"
    assert dumped["spec"]["databaseGuid"] == "database-mock"
