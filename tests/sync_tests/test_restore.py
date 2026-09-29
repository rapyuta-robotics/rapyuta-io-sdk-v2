import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import Restore, RestoreList
from tests.data import (
    restore_body,
    restore_migration_body,
    restore_model_mock,
    restorelist_model_mock,
)
from tests.utils.fixtures import client


def test_list_restores_success(client, restorelist_model_mock, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=restorelist_model_mock,
    )

    response = client.list_restores(database="orders-db")

    assert isinstance(response, RestoreList)
    assert len(response.items) == 1
    restore = response.items[0]
    assert restore.metadata.name == "orders-db-restore"
    assert restore.spec.source.type == "backup"
    assert restore.status.phase == "Completed"
    # The pointer's list of what actually landed, not what was asked for.
    assert restore.status.restored_databases == ["orders"]

    # Restore is a sub-resource: the target database is in the route, not a filter.
    assert "/v2/databases/orders-db/restores/" in mock_get.call_args.kwargs["url"]


def test_get_restore_success(client, restore_model_mock, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=restore_model_mock,
    )

    response = client.get_restore(database="orders-db", name="orders-db-restore")

    assert isinstance(response, Restore)
    assert response.spec.restore_image.endswith("restore:17-latest")
    assert response.spec.source.backup_run_id == "20260101T020000"
    # Signed download links never reach a user-facing read.
    assert response.spec.source.archives[0].url is None


def test_get_restore_not_found(client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "restore not found"},
    )

    with pytest.raises(Exception) as exc:
        client.get_restore(database="orders-db", name="notfound")

    assert str(exc.value) == "restore not found"


def test_create_restore_success(
    client, restore_body, restore_model_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=202,
        json=restore_model_mock,
    )

    response = client.create_restore(body=restore_body)

    assert isinstance(response, Restore)
    assert response.metadata.name == "orders-db-restore"
    # The target database comes from the spec and lands in the route.
    assert "/v2/databases/orders-db/restores/" in mock_post.call_args.kwargs["url"]

    sent = mock_post.call_args.kwargs["json"]
    assert sent["spec"]["source"]["fileUpload"] == "fileupload-mock1234"
    assert sent["spec"]["options"]["noOwner"] is True


def test_create_restore_migration_source(
    client, restore_migration_body, restore_model_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=202,
        json=restore_model_mock,
    )

    client.create_restore(body=restore_migration_body)

    # A migration is the same operation with a dataDirectory source.
    sent = mock_post.call_args.kwargs["json"]
    assert sent["spec"]["source"]["type"] == "dataDirectory"
    assert sent["spec"]["source"]["oldDataDirectory"] == "/opt/rapyuta/volumes/orders-db"
    assert sent["spec"]["source"]["sourceVersion"] == "17"
    assert "/v2/databases/orders-db-v18/restores/" in mock_post.call_args.kwargs["url"]


def test_create_restore_requires_target_database(client, mocker: MockFixture):
    mocker.patch("httpx.Client.post")

    body = {
        "metadata": {"name": "orphan-restore"},
        "spec": {"source": {"type": "backup", "backupName": "orders-nightly"}},
    }

    # Without a target there is no route to post to, and a restore always runs
    # against a live database.
    with pytest.raises(ValueError):
        client.create_restore(body=body)


def test_create_restore_conflict(client, restore_body, mocker: MockFixture):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "a restore is already in progress for this database"},
    )

    # Two concurrent pg_restores into one live cluster is data loss, so the
    # apiserver refuses the second.
    with pytest.raises(Exception) as exc:
        client.create_restore(body=restore_body)

    assert "already in progress" in str(exc.value)
