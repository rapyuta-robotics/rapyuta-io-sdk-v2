import httpx
import pytest

# ruff: noqa: F811, F401
from pytest_mock import MockFixture
from rapyuta_io_sdk_v2.exceptions import UnauthorizedAccessError
from tests.data.mock_data import mock_response_user, user_body
from tests.utils.fixtures import client


def test_get_user_success(client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "User",
            "metadata": {"name": "test user", "guid": "mock_user_guid"},
            "spec": {
                "emailID": "test.user@example.com",
                "firstName": "Test",
                "lastName": "User",
                "userGUID": "mock_user_guid",
                "role": "admin",
            },
        },
    )

    response = client.get_user()
    assert response.metadata.name == "test user"
    assert response.metadata.guid == "mock_user_guid"
    assert response.spec.emailID == "test.user@example.com"


def test_get_user_unauthorized(client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        client.get_user()
    assert "user cannot be authenticated" in str(exc.value)


def test_update_user_success(client, user_body, mock_response_user, mocker: MockFixture):
    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=mock_response_user,
    )
    response = client.update_user(body=user_body)
    assert response.metadata.name == "test user"
    assert response.metadata.guid == "mock_user_guid"
    assert response.spec.emailID == "test.user@example.com"


def test_update_user_unauthorized(client, user_body, mocker: MockFixture):
    mock_put = mocker.patch("httpx.Client.put")

    mock_put.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        client.update_user(user_body)
    assert "user cannot be authenticated" in str(exc.value)
