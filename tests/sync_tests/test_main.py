import httpx
import pytest
from pytest_mock import MockFixture

from tests.utils.fixtures import client  # noqa: F401


def test_get_auth_token_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=200,
        json={
            "success": True,
            "data": {
                "token": "mock_token",
            },
        },
    )

    # Call the get_auth_token method
    response = client.get_auth_token(email="mock_email", password="mock_password")

    assert response == "mock_token"


def test_login_success(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = None

    # Mock the `get_auth_token` method
    mocker.patch.object(client, "get_auth_token", return_value="mock_token_2")

    # Call the login method
    client.login(email="mock_email", password="mock_password")

    assert client.config.auth_token == "mock_token_2"


def test_login_failure(client, mocker: MockFixture):  # noqa: F811
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = None

    mocker.patch.object(
        client,
        "get_auth_token",
        side_effect=Exception("unauthorized permission access"),
    )

    # Call the login method
    with pytest.raises(Exception) as e:
        client.login(email="mock_email", password="mock_password")

    assert str(e.value) == "unauthorized permission access"
