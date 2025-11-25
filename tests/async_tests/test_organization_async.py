from asyncmock import AsyncMock
import httpx
import pytest

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models.organization import Organization
from tests.data.mock_data import mock_response_organization, organization_body
from tests.utils.fixtures import async_client as client


@pytest.mark.asyncio
async def test_get_organization_success(
    client, mock_response_organization, mocker: AsyncMock
):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    # Use mock_response_organization fixture for GET response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=mock_response_organization,
    )

    response = await client.get_organization()

    # Validate that response is an Organization model object
    assert isinstance(response, Organization)
    assert response.metadata.name == "test-org"
    assert response.metadata.guid == "org-testorg123456789abcdef"
    assert len(response.spec.members) == 4
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
async def test_get_organization_unauthorized(client, mocker: AsyncMock):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "user is not part of organization"},
    )

    with pytest.raises(Exception) as exc:
        await client.get_organization()

    assert str(exc.value) == "user is not part of organization"


@pytest.mark.asyncio
async def test_update_organization_success(
    client,
    mock_response_organization,
    organization_body,
    mocker: AsyncMock,
):
    mock_put = mocker.patch("httpx.AsyncClient.put")

    mock_put.return_value = httpx.Response(
        status_code=200,
        json=mock_response_organization,
    )

    response = await client.update_organization(
        organization_guid="org-testorg123456789abcdef",
        body=organization_body,
    )

    # Validate that response is an Organization model object
    assert isinstance(response, Organization)
    assert response.metadata.name == "test-org"
    assert response.metadata.guid == "org-testorg123456789abcdef"
    assert len(response.spec.members) == 4
    # Verify admin member
    assert response.spec.members[1].roleNames == ["rio-org_admin", "rio-org_member"]
    # Verify regular member
    assert response.spec.members[2].roleNames == ["rio-org_member"]
