import httpx
import pytest

# ruff: noqa: F811, F401
from pytest_mock import MockFixture
from rapyuta_io_sdk_v2.exceptions import UnauthorizedAccessError
from tests.data.mock_data import mock_response_user, user_body
from tests.utils.fixtures import client


def test_get_user_success(client, mock_response_user, mocker: MockFixture):
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
    assert len(response.spec.projects) == 2
    assert response.spec.projects[0].name == "test-project1"
    assert response.spec.projects[0].role_names == ["project_admin", "project_member"]
    assert len(response.spec.organizations) == 1
    assert response.spec.organizations[0].name == "test-org"
    assert len(response.spec.user_groups) == 1


def test_get_user_unauthorized(client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        client.get_user(email_id="test.user@example.com")
    assert "user cannot be authenticated" in str(exc.value)


def test_update_user_success(client, user_body, mock_response_user, mocker: MockFixture):
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


def test_update_user_unauthorized(client, user_body, mocker: MockFixture):
    mock_put = mocker.patch("httpx.Client.put")

    mock_put.return_value = httpx.Response(
        status_code=401,
        json={"error": "user cannot be authenticated"},
    )

    with pytest.raises(UnauthorizedAccessError) as exc:
        client.update_user(email_id="test.user@example.com", body=user_body)
    assert "user cannot be authenticated" in str(exc.value)
