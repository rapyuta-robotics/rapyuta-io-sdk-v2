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

from rapyuta_io_sdk_v2.exceptions import (
    HttpNotFoundError,
    InternalServerError,
    UnauthorizedAccessError,
)
from rapyuta_io_sdk_v2.models import SSHKeySignResponse

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import AsyncClient


@pytest.mark.asyncio
async def test_sign_ssh_public_key_success(
    *,
    async_client: AsyncClient,
    ssh_key_sign_request_body: dict[str, Any],
    ssh_key_sign_response_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
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
    *,
    async_client: AsyncClient,
    ssh_key_sign_response_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
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
    assert (
        call_kwargs.kwargs["json"]["publicKey"] == "ssh-rsa AAAAB3... user@example.com"
    )


@pytest.mark.asyncio
async def test_sign_ssh_public_key_unauthorized(
    *,
    async_client: AsyncClient,
    ssh_key_sign_request_body: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        await async_client.sign_ssh_public_key(
            body=ssh_key_sign_request_body,
        )

    assert str(exc.value) == "unauthorized"


@pytest.mark.asyncio
async def test_sign_ssh_public_key_not_found(
    *,
    async_client: AsyncClient,
    ssh_key_sign_request_body: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        await async_client.sign_ssh_public_key(
            body=ssh_key_sign_request_body,
        )

    assert str(exc.value) == "not found"


@pytest.mark.asyncio
async def test_sign_ssh_public_key_server_error(
    *,
    async_client: AsyncClient,
    ssh_key_sign_request_body: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = httpx.Response(
        status_code=500,
        json={"error": "internal server error"},
    )

    with pytest.raises(InternalServerError) as exc:
        await async_client.sign_ssh_public_key(
            body=ssh_key_sign_request_body,
        )

    assert str(exc.value) == "internal server error"
