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

from rapyuta_io_sdk_v2.exceptions import HttpAlreadyExistsError, HttpNotFoundError
from rapyuta_io_sdk_v2.models import (
    StaticRoute,
    StaticRouteList,
)

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import Client


def test_list_staticroutes_success(
    *, client: Client, staticroutelist_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=staticroutelist_model_mock,
    )

    # Call the list_staticroutes method
    response = client.list_staticroutes()

    # Validate the response
    assert isinstance(response, StaticRouteList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    staticroute = response.items[0]
    assert staticroute.metadata.guid == "staticroute-aaaaaaaaaaaaaaaaaaaa"
    assert staticroute.metadata.name == "test-staticroute"
    assert staticroute.kind == "StaticRoute"


def test_list_staticroutes_not_found(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        client.list_staticroutes()

    assert str(exc.value) == "not found"


def test_create_staticroute_success(
    *,
    client: Client,
    staticroute_body: dict[str, Any],
    staticroute_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=staticroute_model_mock,
    )

    # Call the create_staticroute method
    response = client.create_staticroute(
        body=StaticRoute.model_validate(staticroute_body)
    )

    # Validate the response
    assert isinstance(response, StaticRoute)
    assert response.metadata.guid == "staticroute-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test-staticroute"


def test_create_staticroute_bad_request(
    *, client: Client, staticroute_body: dict[str, Any], mocker: MockFixture
) -> None:
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "already exists"},
    )

    with pytest.raises(HttpAlreadyExistsError) as exc:
        client.create_staticroute(body=StaticRoute.model_validate(staticroute_body))

    assert str(exc.value) == "already exists"


def test_get_staticroute_success(
    *, client: Client, staticroute_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=staticroute_model_mock,
    )

    # Call the get_staticroute method
    response = client.get_staticroute(name="mock_staticroute_name")

    # Validate the response
    assert isinstance(response, StaticRoute)
    assert response.metadata.guid == "staticroute-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test-staticroute"


def test_update_staticroute_success(
    *,
    client: Client,
    staticroute_body: dict[str, Any],
    staticroute_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=staticroute_model_mock,
    )

    # Call the update_staticroute method
    response = client.update_staticroute(
        name="mock_staticroute_name", body=StaticRoute.model_validate(staticroute_body)
    )

    # Validate the response
    assert isinstance(response, StaticRoute)
    assert response.metadata.guid == "staticroute-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test-staticroute"


def test_delete_staticroute_success(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_staticroute method
    response = client.delete_staticroute(name="mock_staticroute_name")

    # Validate the response
    assert response is None
