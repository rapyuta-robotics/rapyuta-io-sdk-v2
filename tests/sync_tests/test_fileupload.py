import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import FileUpload, FileUploadList, SharedURL, SharedURLList
from tests.data.mock_data import (
    fileupload_body,
    fileupload_model_mock,
    fileuploadlist_model_mock,
    sharedurl_body,
    sharedurl_model_mock,
    sharedurllist_model_mock,
)
from tests.utils.fixtures import client


MOCK_DEVICE_GUID = "device-mockdevice12345678910"
MOCK_FILEUPLOAD_GUID = "fileupload-mockupload12345678"
MOCK_SHAREDURL_GUID = "sharedurl-mocksharedurl123456"


def test_list_fileuploads_success(client, fileuploadlist_model_mock, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=fileuploadlist_model_mock,
    )

    response = client.list_fileuploads(device_guid=MOCK_DEVICE_GUID)

    assert isinstance(response, FileUploadList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    fileupload = response.items[0]
    assert fileupload.metadata.guid == MOCK_FILEUPLOAD_GUID
    assert fileupload.kind == "DeviceFileUpload"


def test_list_fileuploads_not_found(client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        client.list_fileuploads(device_guid=MOCK_DEVICE_GUID)

    assert str(exc.value) == "not found"


def test_get_fileupload_success(client, fileupload_model_mock, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=fileupload_model_mock,
    )

    response = client.get_fileupload(
        device_guid=MOCK_DEVICE_GUID,
        guid=MOCK_FILEUPLOAD_GUID,
    )

    assert isinstance(response, FileUpload)
    assert response.metadata.guid == MOCK_FILEUPLOAD_GUID
    assert response.spec.file_path == "/home/user/data/sensor_data.log"


def test_get_fileupload_not_found(client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "fileupload not found"},
    )

    with pytest.raises(Exception) as exc:
        client.get_fileupload(device_guid=MOCK_DEVICE_GUID, guid=MOCK_FILEUPLOAD_GUID)

    assert str(exc.value) == "fileupload not found"


def test_create_fileupload_success(
    client, fileupload_body, fileupload_model_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=201,
        json=fileupload_model_mock,
    )

    response = client.create_fileupload(
        device_guid=MOCK_DEVICE_GUID,
        body=fileupload_body,
        project_guid="mock_project_guid",
    )

    assert isinstance(response, FileUpload)
    assert response.metadata.guid == MOCK_FILEUPLOAD_GUID
    assert response.spec.file_path == "/home/user/data/sensor_data.log"


def test_delete_fileupload_success(client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.Client.delete")

    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    response = client.delete_fileupload(
        device_guid=MOCK_DEVICE_GUID,
        guid=MOCK_FILEUPLOAD_GUID,
    )

    assert response is None


def test_delete_fileupload_not_found(client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.Client.delete")

    mock_delete.return_value = httpx.Response(
        status_code=404,
        json={"error": "fileupload not found"},
    )

    with pytest.raises(Exception) as exc:
        client.delete_fileupload(device_guid=MOCK_DEVICE_GUID, guid=MOCK_FILEUPLOAD_GUID)

    assert str(exc.value) == "fileupload not found"


def test_cancel_fileupload_success(client, mocker: MockFixture):
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=204,
    )

    response = client.cancel_fileupload(
        device_guid=MOCK_DEVICE_GUID,
        guid=MOCK_FILEUPLOAD_GUID,
    )

    assert response is None


def test_download_fileupload_success(client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json={"url": "https://storage.example.com/signed-url"},
    )

    response = client.download_fileupload(
        device_guid=MOCK_DEVICE_GUID,
        guid=MOCK_FILEUPLOAD_GUID,
    )

    assert response["url"] == "https://storage.example.com/signed-url"


# SharedURL Tests
def test_list_sharedurls_success(client, sharedurllist_model_mock, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=sharedurllist_model_mock,
    )

    response = client.list_sharedurls(fileupload_guid=MOCK_FILEUPLOAD_GUID)

    assert isinstance(response, SharedURLList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    sharedurl = response.items[0]
    assert sharedurl.metadata.guid == MOCK_SHAREDURL_GUID
    assert sharedurl.kind == "DeviceSharedURL"


def test_create_sharedurl_success(
    client, sharedurl_body, sharedurl_model_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=201,
        json=sharedurl_model_mock,
    )

    response = client.create_sharedurl(
        fileupload_guid=MOCK_FILEUPLOAD_GUID,
        body=sharedurl_body,
    )

    assert isinstance(response, SharedURL)
    assert response.metadata.guid == MOCK_SHAREDURL_GUID


def test_get_sharedurl_redirect(client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=302,
        headers={"Location": "https://storage.example.com/signed-download-url"},
    )

    response = client.get_sharedurl(url_guid=MOCK_SHAREDURL_GUID)

    assert response.status_code == 302
    assert "Location" in response.headers


def test_list_fileuploads_with_filters(
    client, fileuploadlist_model_mock, mocker: MockFixture
):
    """Test list_fileuploads with status and guids filters."""
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=fileuploadlist_model_mock,
    )

    response = client.list_fileuploads(
        device_guid=MOCK_DEVICE_GUID,
        guids=[MOCK_FILEUPLOAD_GUID],
        status=["PENDING", "COMPLETED"],
        cont=0,
        limit=10,
    )

    assert isinstance(response, FileUploadList)
    # Verify the call was made with correct params
    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args
    assert "params" in call_kwargs.kwargs
    assert call_kwargs.kwargs["params"]["guids"] == [MOCK_FILEUPLOAD_GUID]
    assert call_kwargs.kwargs["params"]["status"] == ["PENDING", "COMPLETED"]


def test_create_fileupload_with_dict(client, fileupload_model_mock, mocker: MockFixture):
    """Test create_fileupload with dict input instead of model."""
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=201,
        json=fileupload_model_mock,
    )

    body_dict = {
        "apiVersion": "api.rapyuta.io/v2",
        "kind": "DeviceFileUpload",
        "spec": {
            "file_path": "/home/user/data/sensor_data.log",
        },
    }

    response = client.create_fileupload(
        device_guid=MOCK_DEVICE_GUID,
        body=body_dict,
    )

    assert isinstance(response, FileUpload)
    assert response.metadata.guid == MOCK_FILEUPLOAD_GUID


def test_create_sharedurl_with_dict(client, sharedurl_model_mock, mocker: MockFixture):
    """Test create_sharedurl with dict input instead of model."""
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=201,
        json=sharedurl_model_mock,
    )

    body_dict = {
        "apiVersion": "api.rapyuta.io/v2",
        "kind": "DeviceSharedURL",
        "spec": {
            "expiryTime": "2026-01-28T10:00:00Z",
        },
    }

    response = client.create_sharedurl(
        fileupload_guid=MOCK_FILEUPLOAD_GUID,
        body=body_dict,
    )

    assert isinstance(response, SharedURL)
    assert response.metadata.guid == MOCK_SHAREDURL_GUID


def test_cancel_fileupload_not_found(client, mocker: MockFixture):
    """Test cancel_fileupload when fileupload not found."""
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=404,
        json={"error": "fileupload not found"},
    )

    with pytest.raises(Exception) as exc:
        client.cancel_fileupload(
            device_guid=MOCK_DEVICE_GUID,
            guid=MOCK_FILEUPLOAD_GUID,
        )

    assert str(exc.value) == "fileupload not found"


def test_create_fileupload_conflict(client, fileupload_body, mocker: MockFixture):
    """Test create_fileupload when file already exists (409 Conflict)."""
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "file upload already exists"},
    )

    with pytest.raises(Exception) as exc:
        client.create_fileupload(
            device_guid=MOCK_DEVICE_GUID,
            body=fileupload_body,
        )

    assert str(exc.value) == "file upload already exists"


def test_create_sharedurl_invalid_status(client, sharedurl_body, mocker: MockFixture):
    """Test create_sharedurl when file upload is in invalid status."""
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=400,
        json={"error": "cannot create shared URL for file in FAILED status"},
    )

    with pytest.raises(Exception) as exc:
        client.create_sharedurl(
            fileupload_guid=MOCK_FILEUPLOAD_GUID,
            body=sharedurl_body,
        )

    assert "cannot create shared URL" in str(exc.value)


def test_list_sharedurls_with_pagination(
    client, sharedurllist_model_mock, mocker: MockFixture
):
    """Test list_sharedurls with pagination parameters."""
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=sharedurllist_model_mock,
    )

    response = client.list_sharedurls(
        fileupload_guid=MOCK_FILEUPLOAD_GUID,
        cont=10,
        limit=25,
    )

    assert isinstance(response, SharedURLList)
    # Verify pagination params were passed
    call_kwargs = mock_get.call_args
    assert call_kwargs.kwargs["params"]["continue"] == 10
    assert call_kwargs.kwargs["params"]["limit"] == 25


def test_fileupload_with_all_status_types(
    client, fileupload_model_mock, mocker: MockFixture
):
    """Test parsing file uploads with different status types."""
    mock_get = mocker.patch("httpx.Client.get")

    for status in ["PENDING", "IN PROGRESS", "FAILED", "COMPLETED", "CANCELLED"]:
        mock_data = fileupload_model_mock.copy()
        mock_data["status"] = {
            "status": status,
            "total_size": 1024,
            "uploaded_bytes": 512,
        }
        if status == "FAILED":
            mock_data["status"]["error_message"] = "Upload failed"
            mock_data["status"]["error_code"] = "UPLOAD_ERROR"

        mock_get.return_value = httpx.Response(
            status_code=200,
            json=mock_data,
        )

        response = client.get_fileupload(
            device_guid=MOCK_DEVICE_GUID,
            guid=MOCK_FILEUPLOAD_GUID,
        )

        assert response.status.status == status
