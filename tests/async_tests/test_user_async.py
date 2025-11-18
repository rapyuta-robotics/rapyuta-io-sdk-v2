import httpx
import pytest

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.exceptions import UnauthorizedAccessError
from tests.data.mock_data import mock_response_user as mock_response_user, user_body
from tests.utils.fixtures import async_client


@pytest.mark.asyncio
async def test_get_user_success(async_client, mock_response_user, mocker):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=mock_response_user,
    )

    response = await async_client.get_user()
    assert response.metadata.name == "test user"
    assert response.metadata.guid == "mock_user_guid"
    assert response.spec.emailID == "test.user@example.com"


@pytest.mark.asyncio
async def test_get_user_unauthorized(async_client, mocker):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        await async_client.get_user()
    assert "user cannot be authenticated" in str(exc.value)


@pytest.mark.asyncio
async def test_update_user_success(async_client, mock_response_user, user_body, mocker):
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=mock_response_user,
    )
    response = await async_client.update_user(body=user_body)
    assert response.metadata.name == "test user"
    assert response.metadata.guid == "mock_user_guid"
    assert response.spec.emailID == "test.user@example.com"
    assert response.metadata.name == "test user"
    assert response.metadata.guid == "mock_user_guid"
    assert response.spec.emailID == "test.user@example.com"


@pytest.mark.asyncio
async def test_update_user_unauthorized(
    async_client, mock_response_user, user_body, mocker
):
    mock_put = mocker.patch("httpx.AsyncClient.put")

    mock_put.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        await async_client.update_user(user_body)
    assert "user cannot be authenticated" in str(exc.value)
