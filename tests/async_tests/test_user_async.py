import httpx
import pytest

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.exceptions import UnauthorizedAccessError
from tests.data.mock_data import mock_response_user as mock_response_user, user_body, user_permissions_mock
from tests.utils.fixtures import async_client


@pytest.mark.asyncio
async def test_get_user_success(async_client, mock_response_user, mocker):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=mock_response_user,
    )

    response = await async_client.get_user(email_id="test.user@example.com")
    assert response.metadata.name == "test user"
    assert response.metadata.guid == "user-testuser-guid-000000001"
    assert response.spec.email_id == "test.user@example.com"
    assert response.spec.first_name == "Test"
    assert response.spec.last_name == "User"
    assert len(response.spec.projects) == 2
    assert response.spec.projects[0].name == "test-project1"
    assert response.spec.projects[0].role_names == ["project_admin", "project_member"]
    assert len(response.spec.organizations) == 1
    assert response.spec.organizations[0].name == "test-org"
    assert len(response.spec.user_groups) == 1


@pytest.mark.asyncio
async def test_get_user_unauthorized(async_client, mocker):
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        await async_client.get_user(email_id="test.user@example.com")
    assert "user cannot be authenticated" in str(exc.value)


@pytest.mark.asyncio
async def test_update_user_success(async_client, mock_response_user, user_body, mocker):
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=mock_response_user,
    )
    response = await async_client.update_user(
        email_id="test.user@example.com", body=user_body
    )
    assert response.metadata.name == "test user"
    assert response.metadata.guid == "user-testuser-guid-000000001"
    assert response.spec.email_id == "test.user@example.com"
    assert response.spec.first_name == "Test"
    assert response.spec.last_name == "User"


@pytest.mark.asyncio
async def test_update_user_unauthorized(
    async_client, mock_response_user, user_body, mocker
):
    mock_put = mocker.patch("httpx.AsyncClient.put")

    mock_put.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        await async_client.update_user(email_id="test.user@example.com", body=user_body)
    assert "user cannot be authenticated" in str(exc.value)


@pytest.mark.asyncio
async def test_get_user_permissions_success(async_client, user_permissions_mock, mocker):
    """Test async get_user_permissions with successful response."""
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=user_permissions_mock,
    )

    user_guid = "user-testuser-guid-000000001"
    org_guid = "org-testorg123456789abcdef"

    response = await async_client.get_user_permissions(
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


@pytest.mark.asyncio
async def test_get_user_permissions_with_config_org(async_client, user_permissions_mock, mocker):
    """Test async get_user_permissions using organization_guid from config."""
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json=user_permissions_mock,
    )

    user_guid = "user-testuser-guid-000000001"

    # Call without providing organization_guid (should use config)
    response = await async_client.get_user_permissions(user_guid=user_guid)

    assert response.organization is not None
    assert response.projects is not None

    # Verify the request was made
    mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_permissions_unauthorized(async_client, mocker):
    """Test async get_user_permissions with unauthorized error."""
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        await async_client.get_user_permissions(
            user_guid="user-testuser-guid-000000001",
            organization_guid="org-testorg123456789abcdef",
        )
    assert "user cannot be authenticated" in str(exc.value)

