from datetime import datetime, timezone

import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2 import BulkRoleBindingUpdate, RoleBindingList
from rapyuta_io_sdk_v2.exceptions import HttpAlreadyExistsError, MethodNotAllowedError
from tests.utils.fixtures import async_client

SPEC = {
    "roleRef": {"kind": "Role", "name": "rio-project_admin"},
    "subject": {"kind": "User", "name": "engineer@example.com"},
    "domain": {"kind": "Project", "name": "warehouse-prod"},
}


def binding(guid: str = "rb-1", **window) -> dict:
    return {
        "apiVersion": "api.rapyuta.io/v2",
        "kind": "RoleBinding",
        "metadata": {"guid": guid, "organizationGUID": "mock_org_guid"},
        "spec": {**SPEC, **window},
    }


@pytest.mark.asyncio
async def test_update_role_binding_sends_window(async_client, mocker: MockFixture):
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=202,
        json={"newBindings": [binding(notAfter="2026-10-26T08:00:00Z")]},
    )

    result = await async_client.update_role_binding(
        {
            "newBindings": [
                {
                    "metadata": {"organizationGUID": "mock_org_guid"},
                    "spec": {**SPEC, "notAfter": "2026-10-26T17:00:00+09:00"},
                }
            ],
            "oldBindings": [],
        }
    )

    spec = mock_put.call_args.kwargs["json"]["newBindings"][0]["spec"]
    assert spec["notAfter"] == "2026-10-26T17:00:00+09:00"
    assert "notBefore" not in spec

    assert isinstance(result, BulkRoleBindingUpdate)
    created = result.new_bindings[0]
    assert created.metadata.guid == "rb-1"
    assert created.spec.not_after == datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_update_role_binding_response_without_window(
    async_client, mocker: MockFixture
):
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=202, json={"newBindings": [binding()]}
    )

    result = await async_client.update_role_binding(
        {"newBindings": [binding()], "oldBindings": []}
    )

    assert isinstance(result, BulkRoleBindingUpdate)
    assert result.new_bindings[0].spec.not_after is None


@pytest.mark.asyncio
async def test_update_role_binding_bad_request(async_client, mocker: MockFixture):
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=400, json={"error": "notAfter must be in the future"}
    )

    with pytest.raises(MethodNotAllowedError, match="notAfter must be in the future"):
        await async_client.update_role_binding(
            {"newBindings": [binding()], "oldBindings": []}
        )


@pytest.mark.asyncio
async def test_update_role_binding_conflict(async_client, mocker: MockFixture):
    mock_put = mocker.patch("httpx.AsyncClient.put")
    mock_put.return_value = httpx.Response(
        status_code=409, json={"error": "role binding already exists"}
    )

    with pytest.raises(HttpAlreadyExistsError, match="role binding already exists"):
        await async_client.update_role_binding(
            {"newBindings": [binding()], "oldBindings": []}
        )


@pytest.mark.asyncio
async def test_list_role_bindings_exposes_window(async_client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.AsyncClient.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 0},
            "items": [binding("rb-1"), binding("rb-2", notAfter="2026-10-26T08:00:00Z")],
        },
    )

    result = await async_client.list_role_bindings(role_names=["rio-project_admin"])

    assert isinstance(result, RoleBindingList)
    assert result.items[0].spec.not_after is None
    assert result.items[1].spec.not_after == datetime(
        2026, 10, 26, 8, 0, tzinfo=timezone.utc
    )
