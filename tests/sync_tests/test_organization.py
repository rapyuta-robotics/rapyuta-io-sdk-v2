import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models.organization import Organization
from tests.data.mock_data import mock_response_organization, organization_body
from tests.utils.fixtures import client


def test_get_organization_success(
    client, mock_response_organization, mocker: MockFixture
):
    mock_get = mocker.patch("httpx.Client.get")

    # Use mock_response_organization fixture for GET response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=mock_response_organization,
    )

    response = client.get_organization()

    # Validate that response is an Organization model object
    assert isinstance(response, Organization)
    assert response.metadata.name == "test-org"
    assert response.metadata.guid == "mock_org_guid"
    assert len(response.spec.users) == 2
    assert response.spec.users[0].emailID == "test.user1@rapyuta-robotics.com"
    assert response.spec.users[0].roleInOrganization == "viewer"
    assert response.spec.users[1].emailID == "test.user2@rapyuta-robotics.com"
    assert response.spec.users[1].roleInOrganization == "admin"


def test_get_organization_unauthorized(client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "user is not part of organization"},
    )

    with pytest.raises(Exception) as exc:
        client.get_organization()

    assert str(exc.value) == "user is not part of organization"


def test_update_organization_success(
    client,
    mock_response_organization,
    organization_body,
    mocker: MockFixture,
):
    mock_put = mocker.patch("httpx.Client.put")

    mock_put.return_value = httpx.Response(
        status_code=200,
        json=mock_response_organization,
    )

    response = client.update_organization(
        organization_guid="mock_org_guid",
        body=organization_body,
    )

    # Validate that response is an Organization model object
    assert isinstance(response, Organization)
    assert response.metadata.name == "test-org"
    assert response.metadata.guid == "mock_org_guid"
    assert len(response.spec.users) == 2
    assert response.spec.users[0].roleInOrganization == "viewer"
    assert response.spec.users[1].roleInOrganization == "admin"
