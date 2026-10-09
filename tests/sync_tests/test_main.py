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

from typing import TYPE_CHECKING

import httpx
import pytest

from rapyuta_io_sdk_v2.exceptions import UnauthorizedAccessError

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import Client


def test_get_auth_token_success(*, client: Client, mocker: MockFixture) -> None:
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


def test_login_success(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = None

    # Mock the `get_auth_token` method
    mocker.patch.object(client, "get_auth_token", return_value="mock_token_2")

    # Call the login method
    client.login(email="mock_email", password="mock_password")

    assert client.config.auth_token == "mock_token_2"


def test_login_failure(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = None

    mocker.patch.object(
        client,
        "get_auth_token",
        side_effect=UnauthorizedAccessError("unauthorized permission access"),
    )

    # Call the login method
    with pytest.raises(UnauthorizedAccessError) as e:
        client.login(email="mock_email", password="mock_password")

    assert str(e.value) == "unauthorized permission access"
