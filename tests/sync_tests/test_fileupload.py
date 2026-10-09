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

from rapyuta_io_sdk_v2.exceptions import (
    HttpAlreadyExistsError,
    HttpNotFoundError,
    MethodNotAllowedError,
)
from rapyuta_io_sdk_v2.models import (
    FileUpload,
    FileUploadList,
    SharedURL,
    SharedURLList,
)

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import Client

MOCK_DEVICE_GUID = "device-mockdevice12345678910"
MOCK_FILEUPLOAD_GUID = "fileupload-mockupload12345678"
MOCK_SHAREDURL_GUID = "sharedurl-mocksharedurl123456"


def test_list_fileuploads_success(
    *, client: Client, fileuploadlist_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
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


def test_list_fileuploads_not_found(*, client: Client, mocker: MockFixture) -> None:
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        client.list_fileuploads(device_guid=MOCK_DEVICE_GUID)

    assert str(exc.value) == "not found"


def test_get_fileupload_success(
    *, client: Client, fileupload_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
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


def test_get_fileupload_not_found(*, client: Client, mocker: MockFixture) -> None:
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "fileupload not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        client.get_fileupload(device_guid=MOCK_DEVICE_GUID, guid=MOCK_FILEUPLOAD_GUID)

    assert str(exc.value) == "fileupload not found"


def test_create_fileupload_success(
    *,
    client: Client,
    fileupload_body: dict[str, Any],
    fileupload_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
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


def test_delete_fileupload_success(*, client: Client, mocker: MockFixture) -> None:
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


def test_delete_fileupload_not_found(*, client: Client, mocker: MockFixture) -> None:
    mock_delete = mocker.patch("httpx.Client.delete")

    mock_delete.return_value = httpx.Response(
        status_code=404,
        json={"error": "fileupload not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        client.delete_fileupload(
            device_guid=MOCK_DEVICE_GUID, guid=MOCK_FILEUPLOAD_GUID
        )

    assert str(exc.value) == "fileupload not found"


def test_cancel_fileupload_success(*, client: Client, mocker: MockFixture) -> None:
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=204,
    )

    response = client.cancel_fileupload(
        device_guid=MOCK_DEVICE_GUID,
        guid=MOCK_FILEUPLOAD_GUID,
    )

    assert response is None


def test_download_fileupload_success(*, client: Client, mocker: MockFixture) -> None:
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
def test_list_sharedurls_success(
    *, client: Client, sharedurllist_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
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
    *,
    client: Client,
    sharedurl_body: dict[str, Any],
    sharedurl_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
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


def test_get_sharedurl_redirect(*, client: Client, mocker: MockFixture) -> None:
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=302,
        headers={"Location": "https://storage.example.com/signed-download-url"},
    )

    response = client.get_sharedurl(url_guid=MOCK_SHAREDURL_GUID)

    assert response.status_code == httpx.codes.FOUND
    assert "Location" in response.headers


def test_list_fileuploads_with_filters(
    *, client: Client, fileuploadlist_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
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


def test_create_fileupload_with_dict(
    *, client: Client, fileupload_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
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


def test_create_sharedurl_with_dict(
    *, client: Client, sharedurl_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
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


def test_cancel_fileupload_not_found(*, client: Client, mocker: MockFixture) -> None:
    """Test cancel_fileupload when fileupload not found."""
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=404,
        json={"error": "fileupload not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        client.cancel_fileupload(
            device_guid=MOCK_DEVICE_GUID,
            guid=MOCK_FILEUPLOAD_GUID,
        )

    assert str(exc.value) == "fileupload not found"


def test_create_fileupload_conflict(
    *, client: Client, fileupload_body: dict[str, Any], mocker: MockFixture
) -> None:
    """Test create_fileupload when file already exists (409 Conflict)."""
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "file upload already exists"},
    )

    with pytest.raises(HttpAlreadyExistsError) as exc:
        client.create_fileupload(
            device_guid=MOCK_DEVICE_GUID,
            body=fileupload_body,
        )

    assert str(exc.value) == "file upload already exists"


def test_create_sharedurl_invalid_status(
    *, client: Client, sharedurl_body: dict[str, Any], mocker: MockFixture
) -> None:
    """Test create_sharedurl when file upload is in invalid status."""
    mock_post = mocker.patch("httpx.Client.post")

    mock_post.return_value = httpx.Response(
        status_code=400,
        json={"error": "cannot create shared URL for file in FAILED status"},
    )

    with pytest.raises(MethodNotAllowedError) as exc:
        client.create_sharedurl(
            fileupload_guid=MOCK_FILEUPLOAD_GUID,
            body=sharedurl_body,
        )

    assert "cannot create shared URL" in str(exc.value)


def test_list_sharedurls_with_pagination(
    *, client: Client, sharedurllist_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    """Test list_sharedurls with pagination parameters."""
    requested_cont = 10
    requested_limit = 25
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=sharedurllist_model_mock,
    )

    response = client.list_sharedurls(
        fileupload_guid=MOCK_FILEUPLOAD_GUID,
        cont=requested_cont,
        limit=requested_limit,
    )

    assert isinstance(response, SharedURLList)
    # Verify pagination params were passed
    call_kwargs = mock_get.call_args
    assert call_kwargs.kwargs["params"]["continue"] == requested_cont
    assert call_kwargs.kwargs["params"]["limit"] == requested_limit


def test_fileupload_with_all_status_types(
    *, client: Client, fileupload_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
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
