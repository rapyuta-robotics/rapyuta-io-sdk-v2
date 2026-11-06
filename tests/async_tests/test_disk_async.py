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

from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError, UnauthorizedAccessError
from rapyuta_io_sdk_v2.models import (
    Disk,
    DiskList,
)

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import AsyncClient


@pytest.mark.asyncio
async def test_list_disks_success(
    *,
    async_client: AsyncClient,
    disklist_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=disklist_model_mock,
    )

    response = await async_client.list_disks()

    assert isinstance(response, DiskList)
    assert len(response.items) == 1
    assert response.items[0].metadata.name == "mock_disk_1"


@pytest.mark.asyncio
async def test_get_disk_success(
    *, async_client: AsyncClient, disk_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=disk_model_mock,
    )
    response = await async_client.get_disk(name="mock_disk_1")
    assert isinstance(response, Disk)
    assert response.metadata.name == "mock_disk_1"


@pytest.mark.asyncio
async def test_get_disk_not_found(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "disk not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        await async_client.get_disk(name="notfound")

    assert str(exc.value) == "disk not found"


@pytest.mark.asyncio
async def test_create_disk_unauthorized(
    *, async_client: AsyncClient, disk_body: dict[str, Any], mocker: MockFixture
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        await async_client.create_disk(body=Disk.model_validate(disk_body))

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_delete_disk_success(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await async_client.delete_disk(name="mock_disk_1")

    assert response is None
