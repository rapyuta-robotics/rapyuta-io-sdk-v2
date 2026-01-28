import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import ProjectList, Project
from tests.utils.fixtures import async_client
from tests.data import (
    project_body,
    project_model_mock,
    projectlist_model_mock,
)


@pytest.mark.asyncio
async def test_list_projects_success(
    async_client, projectlist_model_mock, mocker: MockFixture
):
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
async def test_get_project_success(async_client, project_model_mock, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=project_model_mock,
    )
    response = await async_client.get_project(project_guid="test-project")
    assert isinstance(response, Project)
    assert response.metadata.name == "test-project"


@pytest.mark.asyncio
async def test_get_project_not_found(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "project not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.get_project(project_guid="notfound")

    assert str(exc.value) == "project not found"


@pytest.mark.asyncio
async def test_create_project_unauthorized(
    async_client, project_body, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.create_project(body=project_body)

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_update_project_success(
    async_client, project_body, project_model_mock, mocker: MockFixture
):
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=project_model_mock,
    )

    response = await async_client.update_project(
        project_guid="test-project", body=project_body
    )

    assert isinstance(response, Project)
    assert response.metadata.name == "test-project"


@pytest.mark.asyncio
async def test_delete_project_success(async_client, mocker: MockFixture):
    mock_delete = mocker.patch("httpx.AsyncClient.delete")
    mock_delete.return_value = httpx.Response(status_code=204, json={"success": True})

    response = await async_client.delete_project(project_guid="test-project")

    assert response is None
