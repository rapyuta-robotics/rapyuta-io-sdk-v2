import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import SSHKeySignResponse
from tests.data.mock_data import ssh_key_sign_request_body, ssh_key_sign_response_mock
from tests.utils.fixtures import client


def test_sign_ssh_public_key_success(
    client, ssh_key_sign_request_body, ssh_key_sign_response_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=200,
        json=ssh_key_sign_response_mock,
    )

    response = client.sign_ssh_public_key(
        body=ssh_key_sign_request_body,
        user_guid="test-user-guid-000000001",
    )

    assert isinstance(response, SSHKeySignResponse)
    assert response.certificate == ssh_key_sign_response_mock["certificate"]

    # Verify the request was made with correct URL and headers
    call_kwargs = mock_post.call_args
    assert "/v2/certs/ssh/sign/" in call_kwargs.kwargs["url"]
    assert call_kwargs.kwargs["headers"]["userguid"] == "test-user-guid-000000001"


def test_sign_ssh_public_key_with_dict_body(
    client, ssh_key_sign_response_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=200,
        json=ssh_key_sign_response_mock,
    )

    response = client.sign_ssh_public_key(
        body={"publicKey": "ssh-rsa AAAAB3... user@example.com"},
        user_guid="test-user-guid-000000001",
    )

    assert isinstance(response, SSHKeySignResponse)
    assert response.certificate == ssh_key_sign_response_mock["certificate"]

    # Verify the JSON payload uses the alias
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["json"]["publicKey"] == "ssh-rsa AAAAB3... user@example.com"


def test_sign_ssh_public_key_without_user_guid(
    client, ssh_key_sign_request_body, ssh_key_sign_response_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=200,
        json=ssh_key_sign_response_mock,
    )

    response = client.sign_ssh_public_key(body=ssh_key_sign_request_body)

    assert isinstance(response, SSHKeySignResponse)
    # Verify userguid header is NOT set when user_guid is not provided
    call_kwargs = mock_post.call_args
    assert "userguid" not in call_kwargs.kwargs["headers"]


def test_sign_ssh_public_key_unauthorized(
    client, ssh_key_sign_request_body, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        client.sign_ssh_public_key(
            body=ssh_key_sign_request_body,
            user_guid="test-user-guid-000000001",
        )

    assert str(exc.value) == "unauthorized"


def test_sign_ssh_public_key_not_found(
    client, ssh_key_sign_request_body, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        client.sign_ssh_public_key(
            body=ssh_key_sign_request_body,
            user_guid="test-user-guid-000000001",
        )

    assert str(exc.value) == "not found"


def test_sign_ssh_public_key_server_error(
    client, ssh_key_sign_request_body, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value = httpx.Response(
        status_code=500,
        json={"error": "internal server error"},
    )

    with pytest.raises(Exception) as exc:
        client.sign_ssh_public_key(
            body=ssh_key_sign_request_body,
            user_guid="test-user-guid-000000001",
        )

    assert str(exc.value) == "internal server error"
