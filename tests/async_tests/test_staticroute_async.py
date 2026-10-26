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
    StaticRoute,
    StaticRouteList,
)

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import AsyncClient


@pytest.mark.asyncio
async def test_list_staticroutes_success(
    *,
    async_client: AsyncClient,
    staticroutelist_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=staticroutelist_model_mock,
    )

    response = await async_client.list_staticroutes()

    assert isinstance(response, StaticRouteList)
    assert len(response.items) == 1
    assert response.items[0].metadata.name == "test-staticroute"


@pytest.mark.asyncio
async def test_get_staticroute_success(
    *,
    async_client: AsyncClient,
    staticroute_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=staticroute_model_mock,
    )
    response = await async_client.get_staticroute(name="test-staticroute")
    assert isinstance(response, StaticRoute)
    assert response.metadata.name == "test-staticroute"


@pytest.mark.asyncio
async def test_get_staticroute_not_found(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "staticroute not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        await async_client.get_staticroute(name="notfound")

    assert str(exc.value) == "staticroute not found"


@pytest.mark.asyncio
async def test_create_staticroute_unauthorized(
    *, async_client: AsyncClient, staticroute_body: dict[str, Any], mocker: MockFixture
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        await async_client.create_staticroute(
            body=StaticRoute.model_validate(staticroute_body)
        )

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_update_staticroute_success(
    *,
    async_client: AsyncClient,
    staticroute_body: dict[str, Any],
    staticroute_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=staticroute_model_mock,
    )

    response = await async_client.update_staticroute(
        name="test-staticroute", body=StaticRoute.model_validate(staticroute_body)
    )

    assert isinstance(response, StaticRoute)
    assert response.metadata.name == "test-staticroute"


@pytest.mark.asyncio
async def test_delete_staticroute_success(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await async_client.delete_staticroute(name="test-staticroute")

    assert response is None
