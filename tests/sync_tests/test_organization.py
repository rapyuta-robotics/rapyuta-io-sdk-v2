import httpx
import pytest
from munch import Munch
from pytest_mock import MockFixture

from tests.data.mock_data import mock_response_organization, organization_body  # noqa: F401
from tests.utils.fixtures import client  # noqa: F401


def test_get_organization_success(client, mocker: MockFixture):  # noqa: F811
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Organization",
            "metadata": {"name": "test-org", "guid": "mock_org_guid"},
        },
    )

    response = client.get_organization()

    assert isinstance(response, Munch)
    assert response["metadata"] == {"name": "test-org", "guid": "mock_org_guid"}


def test_get_organization_unauthorized(client, mocker: MockFixture):  # noqa: F811
    mock_get = mocker.patch("httpx.Client.get")

    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "user is not part of organization"},
    )

    with pytest.raises(Exception) as exc:
        client.get_organization()

    assert str(exc.value) == "user is not part of organization"


def test_update_organization_success(
    client,  # noqa: F811
    mock_response_organization,  # noqa: F811
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

    assert isinstance(response, Munch)
    assert response["metadata"] == {"name": "test-org", "guid": "mock_org_guid"}
