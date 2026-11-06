# Copyright 2026 Rapyuta Robotics

"""Golden contracts from the pinned Device Manager and v1 SDK sources.

Sources: Device Manager 8123388760aca5b81adf903c24619d62705eb495,
SDK v1 739a6fe44600ff0964fa56b04878ddb21e76b5be, core/v2
4338812cda3502f7a2332bd6c6093fc491d179c2. Each case names its controller.
JSON strings make the stored wire fixtures immutable; callers decode copies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

DEVICE_GUID = "device-a"
BASE = "/api/device-manager/v0"
DEVICE = {
    "uuid": DEVICE_GUID,
    "name": "robot-alpha",
    "status": "ONLINE",
    "device_version": "3",
    "registration_time": "2026-10-14T00:00:00Z",
    "last_online": None,
    "description": "Warehouse robot",
    "created_by": "operator",
    # DeviceApi._device_fields; tests/api/v0/device_tests.py daemon report.
    "daemons_status": {"tracing": {"enable": True}},
    "labels": [{"id": 1, "key": "fleet", "value": "alpha"}],
    "config_variables": [{"id": 2, "key": "ros_workspace", "value": ""}],
}
TOKEN = {
    "status": "success",
    "response": {
        "data": "fixture-onboarding-token",
        "device_id": DEVICE_GUID,
        "script_command": "sudo bash start -r dockercompose",
    },
}
VPN = {
    "apiVersion": "api.rapyuta.io/v2",
    "kind": "DeviceDaemon",
    "metadata": {"guid": DEVICE_GUID, "name": DEVICE_GUID},
    "spec": {
        "vpn_config": {"enable": True},
        "sshcert_config": {"enable": True},
        "pull_secret": {"registry": "registry.example", "auth": "fake-encoded-auth"},
    },
    "status": {"vpn": {"enable": True, "status": "pending"}},
}
PENDING = {
    "status": "error",
    "response": {"error": "Job not found or incomplete", "data": {}},
}


def success(data: object) -> str:
    """Encode a copied, actual success envelope rather than a synthetic result."""
    return json.dumps({"status": "success", "response": {"data": data}})


@dataclass(frozen=True)
class DeviceCase:
    """One independent controller contract, with immutable wire goldens."""

    name: str
    verb: str
    path: str
    response: str
    source: str
    args: tuple[str | int, ...] = ()
    model: str | None = None
    body: str | None = None
    query: tuple[tuple[str, str], ...] = ()


def case(
    name: str, verb: str, path: str, *, data: object, **kwargs: object
) -> DeviceCase:
    """Build a fixture with the source file identified by operation family."""
    family = {
        "label": "labels",
        "config_variable": "config_variables",
        "onboarding": "auth_keys",
        "command": "cmd",
        "parameters": "parameters",
        "select": "selection",
    }
    source = next((value for key, value in family.items() if key in name), "devices")
    return DeviceCase(
        name=name,
        verb=verb,
        path=path,
        response=success(data),
        source=f"device_manager/api/v0/{source}.py",
        **kwargs,
    )


CASES = (
    case("list_devices", "GET", "/devices/", data=[DEVICE]),
    case(
        "select_devices",
        "POST",
        "/selection/query",
        data=[
            {"uuid": DEVICE_GUID, "id": 7, "name": "robot-alpha", "status": "ONLINE"},
        ],
        model="DeviceSelection",
        body='{"operator":"$and","labels":{"operator":"$eq","args":["fleet","alpha"]}}',
    ),
    case(
        "get_device", "GET", f"/devices/{DEVICE_GUID}", data=DEVICE, args=(DEVICE_GUID,)
    ),
    DeviceCase(
        "create_device",
        "POST",
        "/auth-keys/",
        json.dumps(TOKEN),
        "device_manager/api/v0/auth_keys.py:25",
        model="DeviceCreate",
        body='{"name":"robot-alpha","config_variables":{"runtime_docker":true},"labels":{"fleet":"alpha"}}',
        query=(("download_type", "script"),),
    ),
    DeviceCase(
        "get_device_onboarding",
        "GET",
        f"/auth-keys/{DEVICE_GUID}/token/",
        json.dumps(TOKEN),
        "device_manager/api/v0/auth_keys.py:174",
        args=(DEVICE_GUID,),
    ),
    case(
        "update_device",
        "PUT",
        "/devices/",
        data=DEVICE,
        args=(DEVICE_GUID,),
        model="DeviceUpdate",
        body='{"description":"Warehouse robot"}',
    ),
    case(
        "delete_device",
        "DELETE",
        f"/devices/{DEVICE_GUID}",
        data={},
        args=(DEVICE_GUID,),
    ),
    case(
        "list_device_labels",
        "GET",
        f"/labels/{DEVICE_GUID}/",
        data=DEVICE["labels"],
        args=(DEVICE_GUID,),
    ),
    case(
        "create_device_labels",
        "POST",
        f"/labels/{DEVICE_GUID}",
        data=DEVICE["labels"],
        args=(DEVICE_GUID,),
        model="DeviceLabelsCreate",
        body='{"fleet":"alpha"}',
    ),
    case(
        "update_device_label",
        "PUT",
        "/labels/1",
        data={},
        args=(1,),
        model="DeviceLabelUpdate",
        body='{"value":"beta"}',
    ),
    case("delete_device_label", "DELETE", "/labels/1", data={}, args=(1,)),
    case(
        "list_device_config_variables",
        "GET",
        f"/config_variables/device/{DEVICE_GUID}/",
        data=DEVICE["config_variables"],
        args=(DEVICE_GUID,),
    ),
    case(
        "create_device_config_variable",
        "POST",
        f"/config_variables/device/{DEVICE_GUID}",
        data={"id": 2, "key": "setting", "value": "value"},
        args=(DEVICE_GUID,),
        model="DeviceConfigVariableCreate",
        body='{"key":"setting","value":"value"}',
    ),
    case(
        "update_device_config_variable",
        "PUT",
        "/config_variables/2",
        data={"id": 2, "key": "setting", "value": "new"},
        args=(2,),
        model="DeviceConfigVariableUpdate",
        body='{"value":"new"}',
    ),
    case(
        "delete_device_config_variable",
        "DELETE",
        "/config_variables/2",
        data={},
        args=(2,),
    ),
    case(
        "set_device_vpn",
        "PATCH",
        f"/devices/{DEVICE_GUID}/daemons",
        data=VPN,
        args=(DEVICE_GUID,),
        model="DeviceVPNUpdate",
        body='{"vpn":false}',
    ),
    case(
        "apply_device_parameters",
        "POST",
        "/parameters/",
        data=[
            {"device_id": DEVICE_GUID, "success": False, "error": "Device offline"},
        ],
        model="DeviceParameterApply",
        body='{"device_list":["device-a","missing"]}',
    ),
    case(
        "execute_device_command",
        "POST",
        "/cmd/",
        data={DEVICE_GUID: ""},
        model="DeviceCommand",
        body='{"device_ids":["device-a"],"cmd":"true"}',
    ),
    case(
        "get_device_command_result",
        "GET",
        "/cmd/job123",
        data={DEVICE_GUID: ""},
        args=("job123",),
        model="DeviceCommandResultQuery",
        body='{"device_ids":["device-a"]}',
        query=(("device_id", DEVICE_GUID),),
    ),
    case(
        "migrate_device",
        "PUT",
        f"/devices/{DEVICE_GUID}/migrate",
        data={},
        args=(DEVICE_GUID,),
        model="DeviceMigration",
        body='{"project":"destination"}',
    ),
)

# Command controller/model contract: models/api/v0/cmd.py and Salt return strings.
COMMAND_JOB = success({"jid": "job", "minions": ["a", "b", "c"]})
COMMAND_PARTIAL_BATCHES = (
    success({"b": "ready"}),
    success({"a": ""}),
    success({"c": "ready"}),
)
COMMAND_REFUSALS = tuple(
    (
        status,
        json.dumps(
            {
                "status": "error",
                "response": {
                    "error": "Device offline or operation forbidden",
                    "data": {},
                },
            }
        ),
    )
    for status in (400, 401, 403, 404, 429)
)

# Input and emitted JSON differ only when a nested route default is materialized.
VPN_WIRE_CASES = (
    ('{"vpn":true}', '{"vpn":true}'),
    ('{"vpn":false}', '{"vpn":false}'),
    (
        '{"vpn":true,"config":{"vpn":{}}}',
        '{"vpn":true,"config":{"vpn":{"advertise_routes":false}}}',
    ),
    (
        '{"vpn":true,"config":{"vpn":{"advertise_routes":false}}}',
        '{"vpn":true,"config":{"vpn":{"advertise_routes":false}}}',
    ),
    (
        '{"vpn":true,"config":{"vpn":{"advertise_routes":true}}}',
        '{"vpn":true,"config":{"vpn":{"advertise_routes":true}}}',
    ),
)
VPN_INVALID_BODIES = (
    '{"vpn":false,"config":{"vpn":{"advertise_routes":true}}}',
    '{"vpn":true,"tracing":true}',
    '{"vpn":true,"config":{"vpn":{},"tracing":{}}}',
)
