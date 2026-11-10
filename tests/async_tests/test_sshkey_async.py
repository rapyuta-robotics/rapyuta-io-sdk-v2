import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import SSHKeySignResponse
from tests.utils.fixtures import async_client
from tests.data import ssh_key_sign_request_body, ssh_key_sign_response_mock


@pytest.mark.asyncio
async def test_sign_ssh_public_key_success(
    async_client,
    ssh_key_sign_request_body,
    ssh_key_sign_response_mock,
    mocker: MockFixture,
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=200,
        json=ssh_key_sign_response_mock,
    )

    response = await async_client.sign_ssh_public_key(
        body=ssh_key_sign_request_body,
    )

    assert isinstance(response, SSHKeySignResponse)
    assert response.certificate == ssh_key_sign_response_mock["certificate"]

    call_kwargs = mock_post.call_args
    assert "/v2/certs/ssh/sign/" in call_kwargs.kwargs["url"]


@pytest.mark.asyncio
async def test_sign_ssh_public_key_with_dict_body(
    async_client, ssh_key_sign_response_mock, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=200,
        json=ssh_key_sign_response_mock,
    )

    response = await async_client.sign_ssh_public_key(
        body={"publicKey": "ssh-rsa AAAAB3... user@example.com"},
    )

    assert isinstance(response, SSHKeySignResponse)
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["json"]["publicKey"] == "ssh-rsa AAAAB3... user@example.com"


@pytest.mark.asyncio
async def test_sign_ssh_public_key_unauthorized(
    async_client, ssh_key_sign_request_body, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.sign_ssh_public_key(
            body=ssh_key_sign_request_body,
        )

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_sign_ssh_public_key_not_found(
    async_client, ssh_key_sign_request_body, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.sign_ssh_public_key(
            body=ssh_key_sign_request_body,
        )

    assert str(exc.value) == "not found"


@pytest.mark.asyncio
async def test_sign_ssh_public_key_server_error(
    async_client, ssh_key_sign_request_body, mocker: MockFixture
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=500,
        json={"error": "internal server error"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.sign_ssh_public_key(
            body=ssh_key_sign_request_body,
        )

    assert str(exc.value) == "internal server error"


@pytest.mark.asyncio
async def test_sign_org_ssh_public_key_success(
    async_client,
    ssh_key_sign_request_body,
    ssh_key_sign_response_mock,
    mocker: MockFixture,
):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=200,
        json=ssh_key_sign_response_mock,
    )

    response = await async_client.sign_org_ssh_public_key(
        body=ssh_key_sign_request_body,
    )

    assert isinstance(response, SSHKeySignResponse)
    assert response.certificate == ssh_key_sign_response_mock["certificate"]

    # The organization route is distinct from the project one; hitting the wrong
    # URL would silently issue a certificate with the wrong scope.
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["url"].endswith("/v2/certs/ssh/org/sign/")


@pytest.mark.asyncio
async def test_sign_org_ssh_public_key_unauthorized(
    async_client, ssh_key_sign_request_body, mocker: MockFixture
):
    """A caller without organization-scope permission is rejected."""
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "subject is not authorized for this operation"},
    )

    with pytest.raises(Exception) as exc:
        await async_client.sign_org_ssh_public_key(
            body=ssh_key_sign_request_body,
        )

    assert str(exc.value) == "subject is not authorized for this operation"
