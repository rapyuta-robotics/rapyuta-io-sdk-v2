# Copyright 2026 Rapyuta Robotics

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest
from pydantic import ValidationError

from rapyuta_io_sdk_v2 import AsyncClient, Client
from rapyuta_io_sdk_v2.exceptions import (
    HttpBadRequestError,
    HttpForbiddenError,
    MethodNotAllowedError,
)
from rapyuta_io_sdk_v2.models.database import Database, DatabaseCredentials
from rapyuta_io_sdk_v2.utils import handle_server_errors

if TYPE_CHECKING:
    from typing import Any


def _database(postgres: dict[str, Any]) -> Database:
    return Database.model_validate(
        {
            "metadata": {"name": "orders"},
            "spec": {
                "postgres": {
                    "version": "16",
                    "primary": {"deviceName": "edge"},
                    **postgres,
                }
            },
        }
    )


def _literal() -> dict[str, str]:
    return {"username": "test-admin", "password": "test-private-password"}


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.asyncio
async def test_requests_send_exact_literal_credentials(
    mode: str, operation: str
) -> None:
    body = _database({"credentials": _literal()})
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = body.model_dump(mode="json", by_alias=True)
        response["spec"]["postgres"]["credentials"] = {"username": "", "password": ""}
        return httpx.Response(202, json=response)

    if mode == "sync":
        client = Client()
        client.c.close()
        with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
            client.c = transport
            result = (
                client.create_database(body)
                if operation == "create"
                else client.update_database("orders", body)
            )
    else:
        client = AsyncClient()
        await client.c.aclose()
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond)
        ) as transport:
            client.c = transport
            result = (
                await client.create_database(body)
                if operation == "create"
                else await client.update_database("orders", body)
            )
    assert len(requests) == 1
    assert requests[0].method == ("POST" if operation == "create" else "PUT")
    suffix = "" if operation == "create" else "orders/"
    assert requests[0].url.path == f"/v2/databases/{suffix}"
    payload = json.loads(requests[0].content)
    expected = body.model_dump(mode="json", by_alias=True)
    expected["spec"]["postgres"]["credentials"] = _literal()
    assert payload == expected
    assert not result.spec.postgres.credentials.password


def test_literal_credentials_redacted_except_explicit_wire_payload() -> None:
    credentials = DatabaseCredentials(**_literal())
    body = _database({"credentials": credentials})
    for value in _literal().values():
        assert value not in repr(body)
        assert value not in repr(credentials)
        assert value not in repr(body.model_dump())
        assert value not in body.model_dump_json()
    assert (
        body.to_request_payload(creating=True)["spec"]["postgres"]["credentials"]
        == _literal()
    )


@pytest.mark.parametrize(
    "credentials", [None, {}, {"username": "x"}, {"password": "x"}]
)
def test_missing_fields_fail_without_revealing_input(credentials: object) -> None:
    if credentials is None:
        with pytest.raises(ValueError, match="requires credentials"):
            _database({}).to_request_payload(creating=True)
        return
    with pytest.raises(ValidationError):
        _database({"credentials": credentials})


@pytest.mark.parametrize("field", ["username", "password"])
def test_empty_credentials_are_readable_but_cannot_create(field: str) -> None:
    credentials = _literal()
    credentials[field] = ""
    body = _database({"credentials": credentials})
    with pytest.raises(ValueError, match="requires credentials"):
        body.to_request_payload(creating=True)


@pytest.mark.parametrize("value", [{"name": "secret", "key": "password"}, 123])
def test_literal_credentials_never_coerce_refs_or_numbers(value: object) -> None:
    with pytest.raises(ValidationError) as caught:
        _database({"credentials": {"username": "test-admin", "password": value}})
    assert "test-admin" not in str(caught.value)
    assert "input_value" not in str(caught.value)


def test_users_compatibility_is_explicit_and_unchanged() -> None:
    primary = {
        "username": {"name": "database-secret", "key": "user"},
        "password": {"name": "database-secret", "key": "pass"},
    }
    body = _database({"users": {"primary": primary}})
    postgres = body.to_request_payload(creating=True)["spec"]["postgres"]
    assert postgres["credentials"] is None
    assert postgres["users"]["primary"] == {
        name: {**reference, "value": None} for name, reference in primary.items()
    }
    body.spec.postgres.credentials = DatabaseCredentials(**_literal())
    with pytest.raises(ValueError, match="not both"):
        body.to_request_payload(creating=True)


def test_users_resolved_value_is_not_a_credentials_adapter() -> None:
    body = _database(
        {
            "users": {
                "primary": {
                    "username": {"value": "test-admin"},
                    "password": {"value": "test-private-password"},
                }
            }
        }
    )
    with pytest.raises(ValueError, match="requires credentials"):
        body.to_request_payload(creating=True)


@pytest.mark.parametrize(
    "case",
    [
        (400, HttpBadRequestError),
        (403, HttpForbiddenError),
        (405, MethodNotAllowedError),
    ],
)
def test_http_failure_classes_and_numeric_status_are_distinct(case: tuple) -> None:
    status, error_type = case
    with pytest.raises(error_type, match="rejected") as caught:
        handle_server_errors(httpx.Response(status, json={"error": "rejected"}))
    assert type(caught.value) is error_type
    assert caught.value.status_code == status
