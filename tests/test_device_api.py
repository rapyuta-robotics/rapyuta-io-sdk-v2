# Copyright 2026 Rapyuta Robotics

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

import httpx
import pytest
from pydantic import Field

from rapyuta_io_sdk_v2 import Configuration
from rapyuta_io_sdk_v2.exceptions import (
    HttpNotFoundError,
    MethodNotAllowedError,
    UnknownError,
    ValidationError,
)
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.device import DeviceLabelsCreate, DeviceListQuery
from rapyuta_io_sdk_v2.models.device_command import DeviceCommand
from rapyuta_io_sdk_v2.utils import handle_server_errors
from tests.data.device_data import PENDING, success

if TYPE_CHECKING:
    from types import ModuleType


@pytest.fixture
def api() -> ModuleType:
    return import_module("rapyuta_io_sdk_v2._device_api")


class Patch(SDKModel):
    """Omission-sensitive fields independent of the future Device contracts."""

    flag: bool = True
    name: str | None = Field(default=None, alias="wireName")
    text: str = "default"


def test_dynamic_core_host_and_existing_resource_routes(api: ModuleType) -> None:
    config = Configuration(core_api_host="https://core.example")
    original = config.hosts["v2api_host"]
    assert api.device_base(config) == "https://core.example/api/device-manager/v0"
    config.hosts["core_api_host"] = "https://other.example/"
    assert api.device_base(config) == "https://other.example/api/device-manager/v0"
    assert config.hosts["v2api_host"] == original
    config.hosts["core_api_host"] = None
    with pytest.raises(ValidationError, match="core_api_host"):
        api.device_base(config)


@pytest.mark.parametrize("value", ["", " ", ".", "..", "a/b", "a\\b", "a\n", 1])
def test_unsafe_routes_fail_locally(api: ModuleType, value: object) -> None:
    with pytest.raises(ValidationError):
        api.routing_id(value)


def test_literal_safe_routes_are_encoded(api: ModuleType) -> None:
    assert api.routing_id("job 123?#") == "job%20123%3F%23"
    assert api.routing_id("device-a") == "device-a"


@pytest.mark.parametrize("value", [0, -1, True, "1", 1.5])
def test_record_ids_are_strict_positive_integers(
    api: ModuleType, value: object
) -> None:
    with pytest.raises(ValidationError):
        api.record_id(value)
    assert api.record_id(1) == "1"


def test_explicit_fields_are_preserved_without_mutation(api: ModuleType) -> None:
    model = Patch(flag=False, name=None, text="")
    assert api.wire_payload(model, Patch) == {
        "flag": False,
        "wireName": None,
        "text": "",
    }
    assert api.wire_payload(Patch(), Patch) == {}
    assert model.model_fields_set == {"flag", "name", "text"}
    with pytest.raises(AttributeError):
        api.wire_payload({}, Patch)


def test_empty_acknowledgment_is_a_named_model(api: ModuleType) -> None:
    module = import_module("rapyuta_io_sdk_v2.models.device")
    response = httpx.Response(200, json={"status": "success", "response": {"data": {}}})
    parsed = api.device_response(response, module.DeviceMutationResponse)
    assert isinstance(parsed.response.data, module.DeviceEmptyData)
    assert parsed.model_dump(mode="json") == response.json()


@pytest.mark.parametrize(
    "body",
    [
        {"status": "error", "response": {"data": {}}},
        {"status": "success", "response": {"data": {"unexpected": True}}},
        {"status": "success", "response": {"data": {}, "error": "refused"}},
        {"data": {}},
    ],
)
def test_invalid_envelopes_never_acknowledge_success(
    api: ModuleType, body: object
) -> None:
    module = import_module("rapyuta_io_sdk_v2.models.device")
    with pytest.raises(UnknownError):
        api.device_response(
            httpx.Response(200, json=body), module.DeviceMutationResponse
        )


def test_bad_json_and_redirects_are_terminal(api: ModuleType) -> None:
    module = import_module("rapyuta_io_sdk_v2.models.device")
    for response in [httpx.Response(200, content=b"not json"), httpx.Response(302)]:
        with pytest.raises(UnknownError):
            api.device_response(response, module.DeviceMutationResponse)


@pytest.mark.parametrize(
    ("status", "kind"),
    [(404, HttpNotFoundError), (400, MethodNotAllowedError), (429, UnknownError)],
)
def test_nested_errors_preserve_sdk_categories(
    status: int, kind: type[Exception]
) -> None:
    response = httpx.Response(
        status, json={"status": "error", "response": {"error": "refused", "data": {}}}
    )
    with pytest.raises(kind, match="refused") as error:
        handle_server_errors(response)
    assert error.value.status_code == status


def test_top_level_errors_keep_precedence() -> None:
    response = httpx.Response(
        404, json={"error": "top", "response": {"error": "nested"}}
    )
    with pytest.raises(HttpNotFoundError, match="top"):
        handle_server_errors(response)


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "error", "response": {"error": "Device offline", "data": {}}},
        {
            "status": "error",
            "response": {"error": "Job not found or incomplete", "data": {"a": "x"}},
        },
        {
            "status": "success",
            "response": {"error": "Job not found or incomplete", "data": {}},
        },
    ],
)
def test_pending_rejects_other_envelopes(
    api: ModuleType, payload: dict[str, object]
) -> None:
    with pytest.raises(MethodNotAllowedError):
        api.command_result(httpx.Response(400, json=payload))


def test_exact_pending_and_timeout_caps(api: ModuleType) -> None:

    result = api.command_result(httpx.Response(400, json=PENDING))
    assert result.status == "error"
    default = httpx.Timeout(connect=1, read=None, write=20, pool=3)
    assert api.command_timeout(default, 2).as_dict() == {
        "connect": 1,
        "read": 2,
        "write": 2,
        "pool": 2,
    }
    assert default.read is None


def test_background_precedence_and_default_emission(api: ModuleType) -> None:

    body = DeviceCommand(device_ids=("jid",), cmd="true", bg=True, run_async=True)
    result = api.command_submission(
        httpx.Response(200, content=success({"jid": ""})), body
    )
    assert result.response.data.root.root == {"jid": ""}
    assert api.command_json(DeviceCommand(device_ids=("a",), cmd="true")) == {
        "device_ids": ["a"],
        "cmd": "true",
        "bg": False,
        "run_async": False,
        "timeout": 300,
        "env": {},
    }


def test_null_list_filter_and_empty_standalone_labels(api: ModuleType) -> None:

    assert api.list_query(DeviceListQuery(name=None)) == {}
    with pytest.raises(ValidationError, match="at least one label"):
        api.labels_payload(DeviceLabelsCreate({}))
