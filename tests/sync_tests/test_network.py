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
from rapyuta_io_sdk_v2.models import Network, NetworkList

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import Client


def test_list_networks_success(
    *, client: Client, networklist_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=networklist_model_mock,
    )

    # Call the list_networks method
    response = client.list_networks()

    # Validate the response
    assert isinstance(response, NetworkList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    network = response.items[0]
    assert network.metadata.guid == "network-aaaaaaaaaaaaaaaaaaaa"
    assert network.metadata.name == "test-network"
    assert network.kind == "Network"
    assert network.spec.runtime == "cloud"
    assert network.status.phase == "InProgress"
    assert network.status.status == "Running"


def test_list_networks_not_found(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    with pytest.raises(HttpNotFoundError) as exc:
        client.list_networks()

    assert str(exc.value) == "not found"


def test_get_network_success(
    *, client: Client, network_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=network_model_mock,
    )

    # Call the get_network method
    response = client.get_network(name="test-network")

    # Validate the response
    assert isinstance(response, Network)
    assert response.metadata.guid == "network-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test-network"
    assert response.spec.runtime == "cloud"
    assert response.status.phase == "InProgress"
    assert response.status.status == "Running"


def test_create_network_success(
    *,
    client: Client,
    network_body: dict[str, Any],
    network_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=network_model_mock,
    )

    # Call the create_network method
    response = client.create_network(body=network_body)

    # Validate the response
    assert isinstance(response, Network)
    assert response.metadata.guid == "network-aaaaaaaaaaaaaaaaaaaa"
    assert response.metadata.name == "test-network"


def test_create_network_failure(
    *, client: Client, network_body: dict[str, Any], mocker: MockFixture
) -> None:
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=409,
        json={"error": "already exists"},
    )

    with pytest.raises(HttpAlreadyExistsError) as exc:
        client.create_network(body=network_body)

    assert str(exc.value) == "already exists"


def test_delete_network_success(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(
        status_code=204,
        json={"success": True},
    )

    # Call the delete_network method
    response = client.delete_network(name="test-network")

    # Validate the response
    assert response is None
