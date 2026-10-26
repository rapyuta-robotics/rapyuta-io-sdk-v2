# Copyright 2026 Rapyuta Robotics
"""Replay actual pinned v1 public operations and canonical controller goldens.

v2 corrects canonical trailing slashes, makes lookup a single snapshot without
redundant jid query, emits command defaults, and leaves metadata/state checks to
the service. Selection is explicit rather than v1's selection-plus-list workflow.
Migration has no v1 manager wrapper and is checked against the controller golden.
"""

from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING

import httpx
import pytest
import requests
from rapyuta_io.clients.device import Device as LegacyDevice
from rapyuta_io.clients.device import DevicePythonVersion
from rapyuta_io.clients.device_manager import DeviceManagerClient
from rapyuta_io.clients.model import Command, DeviceConfig, Label

from tests.data.device_data import BASE, CASES, DEVICE_GUID
from tests.device_contract_support import arguments, verify_request

if TYPE_CHECKING:
    from collections.abc import Callable

    from rapyuta_io_sdk_v2 import Client
    from tests.data.device_data import DeviceCase


@pytest.fixture
def legacy_device() -> LegacyDevice:
    result = LegacyDevice(
        "robot-alpha",
        runtime_docker=True,
        python_version=DevicePythonVersion.PYTHON3,
        labels={"fleet": "alpha"},
    )
    result.uuid = DEVICE_GUID
    result.deviceId = DEVICE_GUID
    result.update(
        {
            "_device_api_host": "https://core",
            "_auth_token": "Bearer fake",
            "_project": "source",
        }
    )
    result.labels = []
    result.config_variables = []
    return result


def legacy_operation(case: DeviceCase, device: LegacyDevice) -> Callable[[], object]:
    manager = DeviceManagerClient("fake", "source", "https://core")
    builders = {
        "list_devices": manager.device_list,
        "get_device": lambda: manager.get_device(DEVICE_GUID, 0),
        "create_device": lambda: manager.create_device(
            LegacyDevice(
                "robot-alpha",
                runtime_docker=True,
                python_version=DevicePythonVersion.PYTHON3,
                labels={"fleet": "alpha"},
            )
        ),
        "get_device_onboarding": device.onboard_script,
        "update_device": device.save,
        "delete_device": lambda: manager.delete_device(DEVICE_GUID),
        "list_device_labels": device.get_labels,
        "create_device_labels": lambda: device.add_label("fleet", "alpha"),
        "update_device_label": lambda: device.update_label(
            Label(id=1, key="fleet", value="beta")
        ),
        "delete_device_label": lambda: device.delete_label(1),
        "list_device_config_variables": device.get_config_variables,
        "create_device_config_variable": lambda: device.add_config_variable(
            "setting", "value"
        ),
        "update_device_config_variable": lambda: device.update_config_variable(
            DeviceConfig(id=2, key="setting", value="new")
        ),
        "delete_device_config_variable": lambda: device.delete_config_variable(2),
        "set_device_vpn": lambda: manager.patch_daemons(DEVICE_GUID, {"vpn": False}),
        "apply_device_parameters": lambda: manager.apply_parameters(
            ["device-a", "missing"]
        ),
        "execute_device_command": lambda: manager.execute_command(
            [DEVICE_GUID], Command("true")
        ),
        "get_device_command_result": lambda: manager.fetch_cmd_result(
            "job123", [DEVICE_GUID]
        ),
    }
    return builders[case.name]


@pytest.mark.usefixtures("device_reference_network_guard")
@pytest.mark.parametrize(
    "case",
    [case for case in CASES if case.name not in {"select_devices", "migrate_device"}],
    ids=lambda case: case.name,
)
def test_actual_v1_public_serialization(
    case: DeviceCase, legacy_device: LegacyDevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[httpx.Request] = []

    def replay(**kwargs: object) -> requests.Response:
        request = httpx.Request(
            kwargs["method"],
            kwargs["url"],
            headers=kwargs["headers"],
            params=kwargs["params"],
            json=kwargs.get("json"),
        )
        captured.append(request)
        response = requests.Response()
        response.status_code = 200
        response.raw = io.BytesIO(case.response.encode())
        return response

    legacy_device.description = "Warehouse robot"
    monkeypatch.setattr(requests, "request", replay)
    legacy_operation(case, legacy_device)()
    assert len(captured) == 1
    request = captured[0]
    assert request.method == case.verb
    assert request.url.path.rstrip("/") == (BASE + case.path).rstrip("/")
    assert request.headers["project"] == "source"
    if case.body and case.name != "get_device_command_result":
        expected = json.loads(case.body)
        actual = json.loads(request.content)
        assert all(actual[key] == value for key, value in expected.items())
    if case.name == "execute_device_command":
        assert json.loads(request.content)["timeout"] == Command("true").timeout
        assert json.loads(request.content)["bg"] is False
    if case.name == "get_device_command_result":
        assert request.url.params["jid"] == "job123"
        assert request.url.params.get_list("device_id") == [DEVICE_GUID]


@pytest.mark.usefixtures("device_reference_network_guard")
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_v2_canonical_golden_replay(client: Client, case: DeviceCase) -> None:
    client.c.close()
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: verify_request(request, case))
    ) as transport:
        client.c = transport
        args, kwargs = arguments(case)
        response = getattr(client, case.name)(*args, **kwargs)
        assert response.model_dump(
            mode="json", by_alias=True, exclude_unset=True
        ) == json.loads(case.response)


@pytest.mark.usefixtures("device_reference_network_guard")
def test_real_network_is_rejected() -> None:
    with pytest.raises(AssertionError, match="must not use live network"):
        requests.get("https://core.invalid", timeout=1)
