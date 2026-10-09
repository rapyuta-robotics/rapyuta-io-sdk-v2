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
from rapyuta_io_sdk_v2.models.organization import Organization

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import AsyncClient


@pytest.mark.asyncio
async def test_get_organization_success(
    *,
    async_client: AsyncClient,
    mock_response_organization: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Use mock_response_organization fixture for GET response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=mock_response_organization,
    )

    response = await async_client.get_organization()

    # Validate that response is an Organization model object
    assert isinstance(response, Organization)
    assert response.metadata.name == "test-org"
    assert response.metadata.guid == "org-testorg123456789abcdef"
    assert len(response.spec.members) == len(
        mock_response_organization["spec"]["members"]
    )
    # Check first member (ServiceAccount)
    assert response.spec.members[0].subject.kind == "ServiceAccount"
    assert response.spec.members[0].subject.name == "test-project-builtin-paramsync-sa"
    assert response.spec.members[0].roleNames == ["rio-org_member"]
    # Check second member (User - admin)
    assert response.spec.members[1].subject.kind == "User"
    assert response.spec.members[1].subject.name == "test.user1@example.com"
    assert response.spec.members[1].roleNames == ["rio-org_admin", "rio-org_member"]
    # Check third member (User - member only)
    assert response.spec.members[2].subject.kind == "User"
    assert response.spec.members[2].subject.name == "test.user2@example.com"
    assert response.spec.members[2].roleNames == ["rio-org_member"]


@pytest.mark.asyncio
async def test_get_organization_unauthorized(
    *, async_client: AsyncClient, mocker: MockFixture
) -> None:
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "user is not part of organization"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        await async_client.get_organization()

    assert str(exc.value) == "user is not part of organization"


@pytest.mark.asyncio
async def test_update_organization_success(
    *,
    async_client: AsyncClient,
    mock_response_organization: dict[str, Any],
    organization_body: dict[str, Any],
    mocker: MockFixture,
) -> None:
    mock_put = mocker.patch("httpx.AsyncClient.put")

    mock_put.return_value = httpx.Response(
        status_code=200,
        json=mock_response_organization,
    )

    response = await async_client.update_organization(
        organization_guid="org-testorg123456789abcdef",
        body=organization_body,
    )

    # Validate that response is an Organization model object
    assert isinstance(response, Organization)
    assert response.metadata.name == "test-org"
    assert response.metadata.guid == "org-testorg123456789abcdef"
    assert len(response.spec.members) == len(
        mock_response_organization["spec"]["members"]
    )
    # Verify admin member
    assert response.spec.members[1].roleNames == ["rio-org_admin", "rio-org_member"]
    # Verify regular member
    assert response.spec.members[2].roleNames == ["rio-org_member"]
