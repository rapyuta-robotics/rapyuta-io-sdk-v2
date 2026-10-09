from __future__ import annotations

from typing import TYPE_CHECKING, Any

# Copyright 2025 Rapyuta Robotics
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
import httpx
import pytest

from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError, UnauthorizedAccessError
from rapyuta_io_sdk_v2.models import (
    FileUpload,
    FileUploadList,
    SharedURL,
    SharedURLList,
)

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import AsyncClient

MOCK_DEVICE_GUID = "device-mockdevice12345678910"
MOCK_FILEUPLOAD_GUID = "fileupload-mockupload12345678"
MOCK_SHAREDURL_GUID = "sharedurl-mocksharedurl123456"


@pytest.mark.asyncio
async def test_list_fileuploads_success(
    *,
    async_client: AsyncClient,
    fileuploadlist_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=fileuploadlist_model_mock,
    )

    response = await async_client.list_fileuploads(device_guid=MOCK_DEVICE_GUID)

    assert isinstance(response, FileUploadList)
    assert len(response.items) == 1
    assert response.items[0].metadata.guid == MOCK_FILEUPLOAD_GUID


@pytest.mark.asyncio
async def test_get_fileupload_success(
    *,
    async_client: AsyncClient,
    fileupload_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=fileupload_model_mock,
    )
    response = await async_client.get_fileupload(
        device_guid=MOCK_DEVICE_GUID,
        guid=MOCK_FILEUPLOAD_GUID,
    )
    assert isinstance(response, FileUpload)
    assert response.metadata.guid == MOCK_FILEUPLOAD_GUID
    assert response.spec.file_path == "/home/user/data/sensor_data.log"


@pytest.mark.asyncio
async def test_get_fileupload_not_found(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "fileupload not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        await async_client.get_fileupload(
            device_guid=MOCK_DEVICE_GUID,
            guid=MOCK_FILEUPLOAD_GUID,
        )

    assert str(exc.value) == "fileupload not found"


@pytest.mark.asyncio
async def test_create_fileupload_success(
    *,
    async_client: AsyncClient,
    fileupload_body: dict[str, Any],
    fileupload_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=fileupload_model_mock,
    )

    response = await async_client.create_fileupload(
        device_guid=MOCK_DEVICE_GUID,
        body=fileupload_body,
    )

    assert isinstance(response, FileUpload)
    assert response.metadata.guid == MOCK_FILEUPLOAD_GUID


@pytest.mark.asyncio
async def test_create_fileupload_unauthorized(
    *, async_client: AsyncClient, fileupload_body: dict[str, Any], mocker: MockFixture
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        await async_client.create_fileupload(
            device_guid=MOCK_DEVICE_GUID,
            body=fileupload_body,
        )

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_delete_fileupload_success(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await async_client.delete_fileupload(
        device_guid=MOCK_DEVICE_GUID,
        guid=MOCK_FILEUPLOAD_GUID,
    )

    assert response is None


@pytest.mark.asyncio
async def test_cancel_fileupload_success(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")

    mock_post.return_value = httpx.Response(
        status_code=204,
    )

    response = await async_client.cancel_fileupload(
        device_guid=MOCK_DEVICE_GUID,
        guid=MOCK_FILEUPLOAD_GUID,
    )

    assert response is None


@pytest.mark.asyncio
async def test_download_fileupload_success(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json={"url": "https://storage.example.com/signed-url"},
    )

    response = await async_client.download_fileupload(
        device_guid=MOCK_DEVICE_GUID,
        guid=MOCK_FILEUPLOAD_GUID,
    )

    assert response["url"] == "https://storage.example.com/signed-url"


# SharedURL Async Tests
@pytest.mark.asyncio
async def test_list_sharedurls_success(
    *,
    async_client: AsyncClient,
    sharedurllist_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=sharedurllist_model_mock,
    )

    response = await async_client.list_sharedurls(fileupload_guid=MOCK_FILEUPLOAD_GUID)

    assert isinstance(response, SharedURLList)
    assert len(response.items) == 1
    assert response.items[0].metadata.guid == MOCK_SHAREDURL_GUID


@pytest.mark.asyncio
async def test_create_sharedurl_success(
    *,
    async_client: AsyncClient,
    sharedurl_body: dict[str, Any],
    sharedurl_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=sharedurl_model_mock,
    )

    response = await async_client.create_sharedurl(
        fileupload_guid=MOCK_FILEUPLOAD_GUID,
        body=sharedurl_body,
    )

    assert isinstance(response, SharedURL)
    assert response.metadata.guid == MOCK_SHAREDURL_GUID


@pytest.mark.asyncio
async def test_get_sharedurl_redirect(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=302,
        headers={"Location": "https://storage.example.com/signed-download-url"},
    )

    response = await async_client.get_sharedurl(url_guid=MOCK_SHAREDURL_GUID)

    assert response.status_code == httpx.codes.FOUND
    assert "Location" in response.headers


@pytest.mark.asyncio
async def test_list_fileuploads_with_filters(
    *,
    async_client: AsyncClient,
    fileuploadlist_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    """Test list_fileuploads with status and guids filters."""
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=fileuploadlist_model_mock,
    )

    response = await async_client.list_fileuploads(
        device_guid=MOCK_DEVICE_GUID,
        guids=[MOCK_FILEUPLOAD_GUID],
        status=["PENDING", "COMPLETED"],
        cont=0,
        limit=10,
    )

    assert isinstance(response, FileUploadList)
    mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_create_fileupload_with_dict(
    *,
    async_client: AsyncClient,
    fileupload_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    """Test create_fileupload with dict input instead of model."""
    mock_post = mocker.patch("httpx.AsyncClient.post")

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

    response = await async_client.create_fileupload(
        device_guid=MOCK_DEVICE_GUID,
        body=body_dict,
    )

    assert isinstance(response, FileUpload)
    assert response.metadata.guid == MOCK_FILEUPLOAD_GUID


@pytest.mark.asyncio
async def test_create_sharedurl_with_dict(
    *,
    async_client: AsyncClient,
    sharedurl_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    """Test create_sharedurl with dict input instead of model."""
    mock_post = mocker.patch("httpx.AsyncClient.post")

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

    response = await async_client.create_sharedurl(
        fileupload_guid=MOCK_FILEUPLOAD_GUID,
        body=body_dict,
    )

    assert isinstance(response, SharedURL)
    assert response.metadata.guid == MOCK_SHAREDURL_GUID


@pytest.mark.asyncio
async def test_delete_fileupload_not_found(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    """Test delete_fileupload when not found."""
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    mock_delete.return_value = httpx.Response(
        status_code=404,
        json={"error": "fileupload not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        await async_client.delete_fileupload(
            device_guid=MOCK_DEVICE_GUID,
            guid=MOCK_FILEUPLOAD_GUID,
        )

    assert str(exc.value) == "fileupload not found"


@pytest.mark.asyncio
async def test_cancel_fileupload_not_found(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    """Test cancel_fileupload when not found."""
    mock_post = mocker.patch("httpx.AsyncClient.post")

    mock_post.return_value = httpx.Response(
        status_code=404,
        json={"error": "fileupload not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        await async_client.cancel_fileupload(
            device_guid=MOCK_DEVICE_GUID,
            guid=MOCK_FILEUPLOAD_GUID,
        )

    assert str(exc.value) == "fileupload not found"


@pytest.mark.asyncio
async def test_list_sharedurls_with_pagination(
    *,
    async_client: AsyncClient,
    sharedurllist_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    """Test list_sharedurls with pagination parameters."""
    requested_cont = 10
    requested_limit = 25
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=sharedurllist_model_mock,
    )

    response = await async_client.list_sharedurls(
        fileupload_guid=MOCK_FILEUPLOAD_GUID,
        cont=requested_cont,
        limit=requested_limit,
    )

    assert isinstance(response, SharedURLList)
    call_kwargs = mock_get.call_args
    assert call_kwargs.kwargs["params"]["continue"] == requested_cont
    assert call_kwargs.kwargs["params"]["limit"] == requested_limit


@pytest.mark.asyncio
async def test_list_sharedurls_not_found(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    """Test list_sharedurls when fileupload not found."""
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "fileupload not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        await async_client.list_sharedurls(fileupload_guid=MOCK_FILEUPLOAD_GUID)

    assert str(exc.value) == "fileupload not found"
