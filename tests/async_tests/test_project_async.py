import pytest
import pytest_asyncio  # noqa: F401
import httpx
from munch import Munch
from asyncmock import AsyncMock

from tests.data.mock_data import project_body
from tests.utils.fixtures import async_client as client  # noqa: F401


@pytest.mark.asyncio
async def test_list_projects_success(client, mocker: AsyncMock):  # noqa: F811
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 1},
            "items": [{"name": "test-project", "guid": "mock_project_guid"}],
        },
    )

    response = await client.list_projects()

    assert isinstance(response, Munch)
    assert response["items"] == [{"name": "test-project", "guid": "mock_project_guid"}]


@pytest.mark.asyncio
async def test_create_project_success(client, mocker: AsyncMock):  # noqa: F811
    mock_post = mocker.patch("httpx.AsyncClient.post")

    mock_post.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Project",
            "metadata": {"name": "test-project", "guid": "mock_project_guid"},
            "spec": {
                "users": [
                    {"userGUID": "mock_user_guid", "emailID": "test.user@example.com"}
                ]
            },
        },
    )

    response = await client.create_project(project_body)

    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "mock_project_guid"


@pytest.mark.asyncio
async def test_get_project_success(client, mocker: AsyncMock):  # noqa: F811
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Project",
            "metadata": {"name": "test-project", "guid": "mock_project_guid"},
        },
    )

    response = await client.get_project("mock_project_guid")

    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "mock_project_guid"


@pytest.mark.asyncio
async def test_update_project_success(client, mocker: AsyncMock):  # noqa: F811
    mock_put = mocker.patch("httpx.AsyncClient.put")

    mock_put.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Project",
            "metadata": {"name": "test-project", "guid": "mock_project_guid"},
        },
    )

    response = await client.update_project("mock_project_guid", project_body)

    assert isinstance(response, Munch)
    assert response["metadata"]["guid"] == "mock_project_guid"


@pytest.mark.asyncio
async def test_delete_project_success(client, mocker: AsyncMock):  # noqa: F811
    mock_delete = mocker.patch("httpx.AsyncClient.delete")

    mock_delete.return_value = httpx.Response(status_code=200, json={"success": True})

    response = await client.delete_project("mock_project_guid")

    assert isinstance(response, Munch)
    assert response["success"] is True
