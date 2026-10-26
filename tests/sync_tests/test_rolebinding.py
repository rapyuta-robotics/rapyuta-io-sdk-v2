import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from pydantic import ValidationError
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2 import BulkRoleBindingUpdate, RoleBinding, RoleBindingList
from rapyuta_io_sdk_v2.exceptions import HttpAlreadyExistsError, MethodNotAllowedError
from rapyuta_io_sdk_v2.models.rolebinding import RoleBindingSpec
from tests.utils.fixtures import client

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


def test_spec_window_parses_aware():
    spec = RoleBindingSpec.model_validate(
        {
            **SPEC,
            "notBefore": "2026-10-26T09:00:00+09:00",
            "notAfter": "2026-10-26T17:00:00+09:00",
        }
    )

    assert spec.not_before == datetime(2026, 10, 26, 0, 0, tzinfo=timezone.utc)
    assert spec.not_after == datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)
    assert spec.not_after.utcoffset() == timedelta(hours=9)


def test_spec_without_window():
    spec = RoleBindingSpec.model_validate(SPEC)

    assert spec.not_before is None
    assert spec.not_after is None


def test_spec_rejects_naive_datetime():
    with pytest.raises(ValidationError, match="must carry a time zone"):
        RoleBindingSpec.model_validate({**SPEC, "notAfter": "2026-10-26T17:00:00"})


def test_spec_accepts_field_names():
    end = datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)
    spec = RoleBindingSpec(
        role_ref={"name": "rio-project_admin"},
        domain={"kind": "Project", "name": "warehouse-prod"},
        subject={"kind": "User", "name": "engineer@example.com"},
        not_after=end,
    )

    assert spec.not_after == end


def test_spec_dump_omits_empty_window():
    dumped = RoleBindingSpec.model_validate(SPEC).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )

    assert "notBefore" not in dumped
    assert "notAfter" not in dumped


def test_spec_dump_emits_rfc3339():
    dumped = RoleBindingSpec.model_validate(
        {**SPEC, "notAfter": "2026-10-26T08:00:00Z"}
    ).model_dump(mode="json", by_alias=True, exclude_none=True)

    assert dumped["notAfter"] == "2026-10-26T08:00:00Z"
    assert "notBefore" not in dumped


def test_manifest_name_is_accepted_and_not_sent():
    rb = RoleBinding.model_validate(
        {**binding(), "metadata": {"name": "engineer-warehouse-admin"}}
    )

    assert rb.metadata.name == "engineer-warehouse-admin"
    assert "name" not in rb.model_dump(by_alias=True)["metadata"]


def test_bulk_update_without_old_bindings():
    update = BulkRoleBindingUpdate.model_validate({"newBindings": [binding()]})

    assert update.old_bindings == []


def test_update_role_binding_sends_window(client, mocker: MockFixture):
    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(
        status_code=202,
        json={"newBindings": [binding(notAfter="2026-10-26T08:00:00Z")]},
    )

    result = client.update_role_binding(
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

    body = mock_put.call_args.kwargs["json"]
    json.dumps(body)
    spec = body["newBindings"][0]["spec"]
    assert spec["notAfter"] == "2026-10-26T17:00:00+09:00"
    assert "notBefore" not in spec

    assert isinstance(result, BulkRoleBindingUpdate)
    created = result.new_bindings[0]
    assert created.metadata.guid == "rb-1"
    assert created.spec.not_after == datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)


def test_update_role_binding_response_without_window(client, mocker: MockFixture):
    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(
        status_code=202, json={"newBindings": [binding()]}
    )

    result = client.update_role_binding({"newBindings": [binding()], "oldBindings": []})

    assert isinstance(result, BulkRoleBindingUpdate)
    assert result.new_bindings[0].spec.not_after is None


def test_update_role_binding_bad_request(client, mocker: MockFixture):
    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(
        status_code=400, json={"error": "notAfter must be in the future"}
    )

    with pytest.raises(MethodNotAllowedError, match="notAfter must be in the future"):
        client.update_role_binding({"newBindings": [binding()], "oldBindings": []})


def test_update_role_binding_conflict(client, mocker: MockFixture):
    mock_put = mocker.patch("httpx.Client.put")
    mock_put.return_value = httpx.Response(
        status_code=409, json={"error": "role binding already exists"}
    )

    with pytest.raises(HttpAlreadyExistsError, match="role binding already exists"):
        client.update_role_binding({"newBindings": [binding()], "oldBindings": []})


def test_list_role_bindings_exposes_window(client, mocker: MockFixture):
    mock_get = mocker.patch("httpx.Client.get")
    mock_get.return_value = httpx.Response(
        status_code=200,
        json={
            "metadata": {"continue": 0},
            "items": [
                binding("rb-1"),
                binding(
                    "rb-2",
                    notBefore="2026-10-26T00:00:00Z",
                    notAfter="2026-10-26T08:00:00Z",
                ),
            ],
        },
    )

    result = client.list_role_bindings(role_names=["rio-project_admin"])

    assert isinstance(result, RoleBindingList)
    assert result.items[0].spec.not_after is None
    assert result.items[1].spec.not_before == datetime(
        2026, 10, 26, 0, 0, tzinfo=timezone.utc
    )
    assert result.items[1].spec.not_after == datetime(
        2026, 10, 26, 8, 0, tzinfo=timezone.utc
    )
