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

from rapyuta_io_sdk_v2.exceptions import UnauthorizedAccessError

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import Client


def test_get_user_success(
    *, client: Client, mock_response_user: dict[str, Any], mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=mock_response_user,
    )

    response = client.get_user(email_id="test.user@example.com")
    assert response.metadata.name == "test user"
    assert response.metadata.guid == "user-testuser-guid-000000001"
    assert response.spec.email_id == "test.user@example.com"
    assert response.spec.first_name == "Test"
    assert response.spec.last_name == "User"
    assert len(response.spec.projects) == len(mock_response_user["spec"]["projects"])
    assert response.spec.projects[0].name == "test-project1"
    assert response.spec.projects[0].role_names == ["project_admin", "project_member"]
    assert len(response.spec.organizations) == 1
    assert response.spec.organizations[0].name == "test-org"
    assert len(response.spec.user_groups) == 1


def test_get_user_unauthorized(*, client: Client, mocker: MockFixture) -> None:
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        client.get_user(email_id="test.user@example.com")
    assert "user cannot be authenticated" in str(exc.value)


def test_update_user_success(
    *,
    client: Client,
    user_body: dict[str, Any],
    mock_response_user: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=mock_response_user,
    )
    response = client.update_user(email_id="test.user@example.com", body=user_body)
    assert response.metadata.name == "test user"
    assert response.metadata.guid == "user-testuser-guid-000000001"
    assert response.spec.email_id == "test.user@example.com"
    assert response.spec.first_name == "Test"
    assert response.spec.last_name == "User"


def test_update_user_unauthorized(
    *, client: Client, user_body: dict[str, Any], mocker: MockFixture
) -> None:
    mock_put = mocker.patch("httpx.Client.put")

    mock_put.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        client.update_user(email_id="test.user@example.com", body=user_body)
    assert "user cannot be authenticated" in str(exc.value)


def test_get_user_permissions_success(
    *, client: Client, user_permissions_mock: dict[str, Any], mocker: MockFixture
) -> None:
    """Test get_user_permissions with successful response."""
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=user_permissions_mock,
    )

    user_guid = "user-testuser-guid-000000001"
    org_guid = "org-testorg123456789abcdef"

    response = client.get_user_permissions(
        user_guid=user_guid,
        organization_guid=org_guid,
    )

    # Verify organization permissions
    assert response.organization is not None
    assert "projects" in response.organization
    assert "create" in response.organization["projects"]
    assert response.organization["projects"]["create"] == ["allowed"]

    # Verify project permissions
    assert response.projects is not None
    assert "project-aaaaaaaaaaaaaaaaaaaa" in response.projects
    assert "deployments" in response.projects["project-aaaaaaaaaaaaaaaaaaaa"]
    assert "create" in response.projects["project-aaaaaaaaaaaaaaaaaaaa"]["deployments"]

    # Verify group permissions
    assert response.groups is not None
    assert "group-aaaaaaaaaaaaaaaaaaaa" in response.groups
    assert "secrets" in response.groups["group-aaaaaaaaaaaaaaaaaaaa"]

    # Verify the request was made with correct headers
    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args[1]
    assert "headers" in call_kwargs
    assert call_kwargs["headers"]["organizationguid"] == org_guid
    assert call_kwargs["headers"]["userguid"] == user_guid


def test_get_user_permissions_with_config_org(
    *, client: Client, user_permissions_mock: dict[str, Any], mocker: MockFixture
) -> None:
    """Test get_user_permissions using organization_guid from config."""
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=user_permissions_mock,
    )

    user_guid = "user-testuser-guid-000000001"

    # Call without providing organization_guid (should use config)
    response = client.get_user_permissions(user_guid=user_guid)

    assert response.organization is not None
    assert response.projects is not None

    # Verify the request was made
    mock_get.assert_called_once()


def test_get_user_permissions_unauthorized(
    *, client: Client, mocker: MockFixture
) -> None:
    """Test get_user_permissions with unauthorized error."""
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        client.get_user_permissions(
            user_guid="user-testuser-guid-000000001",
            organization_guid="org-testorg123456789abcdef",
        )
    assert "user cannot be authenticated" in str(exc.value)
