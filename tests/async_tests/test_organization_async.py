from asyncmock import AsyncMock
import httpx
import pytest
from munch import Munch
from tests.data.mock_data import mock_response_organization, organization_body  # noqa: F401
from tests.utils.fixtures import async_client as client  # noqa: F401


@pytest.mark.asyncio
async def test_get_organization_success(client, mocker: AsyncMock):  # noqa: F811
    mock_get = mocker.patch("httpx.AsyncClient.get")

    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "kind": "Organization",
            "metadata": {"name": "test-org", "guid": "mock_org_guid"},
        },
    )

    response = await client.get_organization()

    assert isinstance(response, Munch)
    assert response["metadata"] == {"name": "test-org", "guid": "mock_org_guid"}


@pytest.mark.asyncio
async def test_get_organization_unauthorized(client, mocker: AsyncMock):  # noqa: F811
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
    client,  # noqa: F811
    mock_response_organization,  # noqa: F811
    mocker: AsyncMock,
):
    mock_put = mocker.patch("httpx.AsyncClient.put")

    mock_put.return_value = httpx.Response(
        status_code=200,
        json=mock_response_organization,
    )

    response = await client.update_organization(
        organization_guid="mock_org_guid",
        body=organization_body,
    )

    assert isinstance(response, Munch)
    assert response["metadata"] == {"name": "test-org", "guid": "mock_org_guid"}
