from asyncmock import AsyncMock
import httpx
import pytest
from munch import Munch

from tests.data.mock_data import mock_response_user, user_body  # noqa: F401
from tests.utils.fixtures import async_client as client  # noqa: F401


@pytest.mark.asyncio
async def test_get_user_success(client, mocker: AsyncMock):  # noqa: F811
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "User",
            "metadata": {"name": "test-org", "guid": "mock_org_guid"},
        },
    )

    response = await client.get_user()

    assert isinstance(response, Munch)
    assert response["metadata"] == {"name": "test-org", "guid": "mock_org_guid"}


@pytest.mark.asyncio
async def test_get_user_unauthorized(client, mocker: AsyncMock):  # noqa: F811
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(Exception) as exc:
        await client.get_user()

    assert str(exc.value) == "user cannot be authenticated"


@pytest.mark.asyncio
async def test_update_user_success(
    client,  # noqa: F811
    mock_response_user,  # noqa: F811
    mocker: AsyncMock,
):
    mock_put = mocker.patch("httpx.AsyncClient.put")

    mock_put.return_value = httpx.Response(
        status_code=200,
        json=mock_response_user,
    )

    response = await client.update_user(
        body=user_body,
    )

    assert isinstance(response, Munch)
    assert response["metadata"] == {"name": "test user", "guid": "mock_user_guid"}


@pytest.mark.asyncio
async def test_update_user_unauthorized(client, mocker: AsyncMock):  # noqa: F811
    mock_put = mocker.patch("httpx.AsyncClient.put")

    mock_put.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(Exception) as exc:
        await client.update_user(user_body)

    assert str(exc.value) == "user cannot be authenticated"
