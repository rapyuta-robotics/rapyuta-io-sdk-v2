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

from rapyuta_io_sdk_v2.exceptions import HttpNotFoundError, UnauthorizedAccessError
from rapyuta_io_sdk_v2.models import Project, ProjectList

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import Client


# Test function for list_projects
def test_list_projects_success(
    *, client: Client, projectlist_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=projectlist_model_mock,
    )

    # Call the list_projects method
    response = client.list_projects()

    # Validate the response
    assert isinstance(response, ProjectList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    project = response.items[0]
    assert project.metadata.guid == "mock_project_guid"
    assert project.metadata.name == "test-project"
    assert project.kind == "Project"


def test_list_projects_unauthorized(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized permission access"},
    )

    # Call the list_projects method
    with pytest.raises(UnauthorizedAccessError) as exc:
        client.list_projects()

    # Validate the exception message
    assert str(exc.value) == "unauthorized permission access"


def test_list_projects_not_found(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    # Call the list_projects method
    with pytest.raises(HttpNotFoundError) as exc:
        client.list_projects()

    # Validate the exception message
    assert str(exc.value) == "not found"


def test_get_project_success(
    *, client: Client, project_model_mock: dict[str, Any], mocker: MockFixture
) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=project_model_mock,
    )

    # Call the get_project method
    response = client.get_project(project_guid="mock_project_guid")

    # Validate the response
    assert isinstance(response, Project)
    assert response.metadata.guid == "mock_project_guid"
    assert response.metadata.name == "test-project"


def test_get_project_not_found(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "project not found"},
    )

    # Call the get_project method
    with pytest.raises(HttpNotFoundError) as exc:
        client.get_project(project_guid="mock_project_guid")

    # Validate the exception message
    assert str(exc.value) == "project not found"


def test_create_project_success(
    *,
    client: Client,
    project_body: dict[str, Any],
    project_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=project_model_mock,
    )

    # Call the create_project method
    response = client.create_project(body=project_body)

    # Validate the response
    assert isinstance(response, Project)
    assert response.metadata.guid == "mock_project_guid"
    assert response.metadata.name == "test-project"


def test_create_project_unauthorized(
    *, client: Client, project_body: dict[str, Any], mocker: MockFixture
) -> None:
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized permission access"},
    )

    # Call the create_project method
    with pytest.raises(UnauthorizedAccessError) as exc:
        client.create_project(body=project_body)

    # Validate the exception message
    assert str(exc.value) == "unauthorized permission access"


def test_update_project_success(
    *,
    client: Client,
    project_body: dict[str, Any],
    project_model_mock: dict[str, Any],
    mocker: MockFixture,
) -> None:
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=project_model_mock,
    )

    # Call the update_project method
    response = client.update_project(
        project_guid="mock_project_guid", body=project_body
    )

    # Validate the response
    assert isinstance(response, Project)
    assert response.metadata.guid == "mock_project_guid"
    assert response.metadata.name == "test-project"


def test_delete_project_success(*, client: Client, mocker: MockFixture) -> None:
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(status_code=200, json={"success": True})

    # Call the delete_project method
    response = client.delete_project(project_guid="mock_project_guid")

    # Validate the response
    assert response is None
