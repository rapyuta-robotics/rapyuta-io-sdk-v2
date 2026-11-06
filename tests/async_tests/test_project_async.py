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
    Project,
    ProjectList,
)

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import AsyncClient


@pytest.mark.asyncio
async def test_list_projects_success(
    *,
    async_client: AsyncClient,
    projectlist_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=projectlist_model_mock,
    )

    response = await async_client.list_projects()

    assert isinstance(response, ProjectList)
    assert len(response.items) == 1
    assert response.items[0].metadata.name == "test-project"


@pytest.mark.asyncio
async def test_get_project_success(
    *,
    async_client: AsyncClient,
    project_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=project_model_mock,
    )
    response = await async_client.get_project(project_guid="test-project")
    assert isinstance(response, Project)
    assert response.metadata.name == "test-project"


@pytest.mark.asyncio
async def test_get_project_not_found(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "project not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        await async_client.get_project(project_guid="notfound")

    assert str(exc.value) == "project not found"


@pytest.mark.asyncio
async def test_create_project_unauthorized(
    *, async_client: AsyncClient, project_body: dict[str, Any], mocker: MockFixture
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        await async_client.create_project(body=Project.model_validate(project_body))

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_update_project_success(
    *,
    async_client: AsyncClient,
    project_body: dict[str, Any],
    project_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=project_model_mock,
    )

    response = await async_client.update_project(
        project_guid="test-project", body=Project.model_validate(project_body)
    )

    assert isinstance(response, Project)
    assert response.metadata.name == "test-project"


@pytest.mark.asyncio
async def test_delete_project_success(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await async_client.delete_project(project_guid="test-project")

    assert response is None
