"""MockTransport coverage for sync and async Device Management operations."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from rapyuta_io_sdk_v2.context import RequestContext
from rapyuta_io_sdk_v2.async_client import AsyncClient
from rapyuta_io_sdk_v2.client import Client
from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.exceptions import BadRequestError, HttpNotFoundError
from rapyuta_io_sdk_v2.models.device import (
    Device,
    DeviceActionResponse,
    DeviceCommand,
    DeviceConfigVariableCreate,
    DeviceConfigVariableUpdate,
    DeviceCreate,
    DeviceCreateResponse,
    DeviceDaemonPatch,
    DeviceLabel,
    DeviceLabelCreate,
    DeviceLabelUpdate,
    DeviceSelectionQuery,
)


class _SyncClient(Client):
    def __init__(self, transport):
        super().__init__(
            config=Configuration(
                load_cli_config=False,
                core_api_host="https://core.example",
                auth_token="test",
                project_guid="project",
            ),
            transport=httpx.Client(transport=transport),
        )


class _AsyncClient(AsyncClient):
    def __init__(self, transport):
        super().__init__(
            config=Configuration(
                load_cli_config=False,
                core_api_host="https://core.example",
                auth_token="test",
                project_guid="project",
            ),
            transport=httpx.AsyncClient(transport=transport),
        )


def _envelope(data, status="success"):
    return {"status": status, "response": {"data": data}}


@pytest.mark.parametrize("async_mode", [False, True])
def test_list_devices_filters_architecture_online_and_uses_v1_envelopes(async_mode):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("selection/query/"):
            return httpx.Response(200, json=_envelope([{"uuid": "d1"}]))
        return httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "uuid": "d1",
                        "name": "selected",
                        "status": "ONLINE",
                        "device_version": "3",
                    },
                    {"uuid": "d2", "name": "offline", "status": "OFFLINE"},
                ]
            ),
        )

    async def run_async():
        client = _AsyncClient(httpx.MockTransport(handler))
        try:
            selected = await client.select_devices(
                DeviceSelectionQuery(
                    operator="$or",
                    specs={
                        "operator": "$or",
                        "args": [
                            {"operator": "$eq", "args": ["cpuarch", "x86_64"]},
                            {"operator": "$eq", "args": ["cpuarch", "amd64"]},
                        ],
                    },
                ),
                context=RequestContext(headers={"X-Trace": "trace"}),
            )
            devices = await client.list_devices(
                name="test",
                online=True,
                context=RequestContext(headers={"X-Trace": "trace"}),
            )
            devices = [
                device for device in devices if device.uuid in {d.uuid for d in selected}
            ]
            assert [device.uuid for device in devices] == ["d1"]
            assert devices[0].python_version == "3"
        finally:
            await client.c.aclose()

    def run_sync():
        client = _SyncClient(httpx.MockTransport(handler))
        try:
            selected = client.select_devices(
                DeviceSelectionQuery(
                    operator="$or",
                    specs={
                        "operator": "$or",
                        "args": [
                            {"operator": "$eq", "args": ["cpuarch", "x86_64"]},
                            {"operator": "$eq", "args": ["cpuarch", "amd64"]},
                        ],
                    },
                ),
                context=RequestContext(headers={"X-Trace": "trace"}),
            )
            devices = client.list_devices(
                name="test",
                online=True,
                context=RequestContext(headers={"X-Trace": "trace"}),
            )
            devices = [
                device for device in devices if device.uuid in {d.uuid for d in selected}
            ]
            assert [device.uuid for device in devices] == ["d1"]
            assert devices[0].python_version == "3"
        finally:
            client.c.close()

    asyncio.run(run_async()) if async_mode else run_sync()
    assert len(requests) == 2
    selection = requests[0]
    assert selection.method == "POST"
    assert selection.headers["X-Trace"] == "trace"
    assert selection.read()
    assert requests[1].url.params["name"] == "test"


@pytest.mark.parametrize("async_mode", [False, True])
def test_device_crud_config_variables_and_labels_wire_payloads(async_mode):
    requests = []

    def handler(request):
        requests.append(request)
        path = request.url.path
        if path.endswith("auth-keys/"):
            return httpx.Response(
                201,
                json={
                    "status": "success",
                    "response": {
                        "data": "token",
                        "device_id": "created",
                        "script_command": "sudo bash start",
                    },
                },
            )
        if path.endswith("config_variables/device/d1"):
            if request.method == "GET":
                return httpx.Response(
                    200, json=_envelope([{"id": 5, "key": "k", "value": "v"}])
                )
            return httpx.Response(
                201, json=_envelope({"id": 6, "key": "new", "value": "value"})
            )
        if path.endswith("config_variables/6"):
            if request.method == "DELETE":
                return httpx.Response(200, json=_envelope({}))
            return httpx.Response(
                200, json=_envelope({"id": 6, "key": "new", "value": "updated"})
            )
        if path.endswith("labels/d1"):
            if request.method == "GET":
                return httpx.Response(
                    200, json=_envelope([{"id": 8, "key": "team", "value": "blue"}])
                )
            return httpx.Response(
                201, json=_envelope([{"id": 9, "key": "team", "value": "red"}])
            )
        if path.endswith("labels/9"):
            return httpx.Response(200, json=_envelope({}))
        if path.endswith("devices/d1") and request.method == "GET":
            return httpx.Response(200, json=_envelope({"uuid": "d1", "name": "robot"}))
        if path.endswith("devices/d1") and request.method == "DELETE":
            return httpx.Response(200, json=_envelope({"status": "success"}))
        return httpx.Response(404, json={"error": "unexpected"})

    async def operations(client):
        assert (await client.get_device("d1")).name == "robot"
        assert await client.create_device(
            DeviceCreate(name="robot")
        ) == DeviceCreateResponse(
            token="token", device_id="created", script_command="sudo bash start"
        )
        assert (await client.list_device_config_variables("d1"))[0].id == 5
        created = await client.create_device_config_variable(
            "d1", DeviceConfigVariableCreate(key="new", value="value")
        )
        assert created.id == 6
        updated = await client.update_device_config_variable(
            DeviceConfigVariableUpdate(id=6, key="new", value="updated")
        )
        assert updated.value == "updated"
        assert await client.delete_device_config_variable(6) is None
        assert (await client.list_device_labels("d1"))[0].key == "team"
        label = await client.create_device_label(
            "d1", DeviceLabelCreate(key="team", value="red")
        )
        assert label.id == 9
        assert await client.update_device_label(
            DeviceLabelUpdate(id=9, key="team", value="green")
        ) == DeviceLabel(id=9, key="team", value="green")
        assert await client.delete_device_label(9) is None
        assert await client.delete_device("d1") is None

    async def run_async():
        client = _AsyncClient(httpx.MockTransport(handler))
        try:
            await operations(client)
        finally:
            await client.c.aclose()

    def run_sync():
        client = _SyncClient(httpx.MockTransport(handler))
        try:
            # Keep the shared assertions simple while invoking the sync API directly.
            assert client.get_device("d1").name == "robot"
            assert client.create_device(DeviceCreate(name="robot")).device_id == "created"
            assert client.list_device_config_variables("d1")[0].id == 5
            created = client.create_device_config_variable(
                "d1", DeviceConfigVariableCreate(key="new", value="value")
            )
            assert created.id == 6
            assert (
                client.update_device_config_variable(
                    DeviceConfigVariableUpdate(id=6, key="new", value="updated")
                ).value
                == "updated"
            )
            assert client.delete_device_config_variable(6) is None
            assert client.list_device_labels("d1")[0].key == "team"
            assert (
                client.create_device_label(
                    "d1", DeviceLabelCreate(key="team", value="red")
                ).id
                == 9
            )
            label = DeviceLabelUpdate(id=9, key="team", value="green")
            assert client.update_device_label(label) == DeviceLabel(
                id=9, key="team", value="green"
            )
            assert client.delete_device_label(9) is None
            assert client.delete_device("d1") is None
        finally:
            client.c.close()

    asyncio.run(run_async()) if async_mode else run_sync()
    bodies = [request for request in requests if request.method in {"POST", "PUT"}]
    create_device_request = next(
        request for request in bodies if request.url.path.endswith("auth-keys/")
    )
    assert create_device_request.url.params["download_type"] == "script"
    assert (
        create_device_request.read()
        == b'{"name":"robot","python_version":"2","config_variables":{},"labels":{}}'
    )
    add_label = next(
        request
        for request in bodies
        if request.method == "POST" and request.url.path.endswith("labels/d1")
    )
    assert add_label.read() == b'{"team":"red"}'


@pytest.mark.parametrize("async_mode", [False, True])
def test_command_submission_and_single_result_fetch(async_mode):
    requests = []
    result_polls = 0

    def handler(request):
        nonlocal result_polls
        requests.append(request)
        if request.url.path.endswith("/cmd/"):
            return httpx.Response(200, json=_envelope({"jid": "job-1"}))
        result_polls += 1
        return httpx.Response(200, json=_envelope({"robot": "done"}))

    async def run_async():
        client = _AsyncClient(httpx.MockTransport(handler))
        try:
            submitted = await client.execute_command(
                ["robot"], DeviceCommand(cmd="uname")
            )
            assert submitted.jid == "job-1"
            result = await client.get_command_result("job-1", ["robot", "robot"])
            assert result.data == {"robot": "done"}
        finally:
            await client.c.aclose()

    def run_sync():
        client = _SyncClient(httpx.MockTransport(handler))
        try:
            submitted = client.execute_command(["robot"], DeviceCommand(cmd="uname"))
            assert submitted.jid == "job-1"
            result = client.get_command_result("job-1", ["robot", "robot"])
            assert result.data == {"robot": "done"}
        finally:
            client.c.close()

    asyncio.run(run_async()) if async_mode else run_sync()
    assert (
        requests[0].read()
        == b'{"cmd":"uname","device_ids":["robot"],"env":{},"bg":false,"run_async":false,"timeout":300}'
    )
    assert requests[1].url.params.get_list("device_id") == ["robot", "robot"]
    assert len(requests) == 2
    assert result_polls == 1


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("status_code", [202, 204])
def test_get_command_result_returns_pending_metadata_once(async_mode, status_code):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status_code)

    async def run_async():
        client = _AsyncClient(httpx.MockTransport(handler))
        try:
            result = await client.get_command_result(
                "job-1",
                ["robot", "robot"],
                context=RequestContext(request_id="trace"),
            )
            assert result.is_pending
            assert result.http_status_code == status_code
            assert "http_status_code" not in result.model_dump()
        finally:
            await client.c.aclose()

    def run_sync():
        client = _SyncClient(httpx.MockTransport(handler))
        try:
            result = client.get_command_result(
                "job-1",
                ["robot", "robot"],
                context=RequestContext(request_id="trace"),
            )
            assert result.is_pending
            assert result.http_status_code == status_code
            assert "http_status_code" not in result.model_dump()
        finally:
            client.c.close()

    asyncio.run(run_async()) if async_mode else run_sync()
    assert len(requests) == 1
    assert requests[0].url.params.get_list("device_id") == ["robot", "robot"]
    assert requests[0].headers["X-Request-ID"] == "trace"


@pytest.mark.parametrize("async_mode", [False, True])
def test_get_command_result_preserves_v1_envelope_pending_status(async_mode):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"status": "pending", "response": {"data": None}})

    async def run_async():
        client = _AsyncClient(httpx.MockTransport(handler))
        try:
            result = await client.get_command_result("job-1", ["robot"])
        finally:
            await client.c.aclose()
        return result

    def run_sync():
        client = _SyncClient(httpx.MockTransport(handler))
        try:
            return client.get_command_result("job-1", ["robot"])
        finally:
            client.c.close()

    result = asyncio.run(run_async()) if async_mode else run_sync()
    assert result.is_pending
    assert result.status is None
    assert result.data is None
    assert result.envelope_status == "pending"
    assert result.http_status_code == 200
    assert len(requests) == 1


@pytest.mark.parametrize("async_mode", [False, True])
def test_apply_parameters_daemon_patch_and_http_errors(async_mode):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("parameters/"):
            return httpx.Response(200, json=_envelope({"applied": True}))
        if request.url.path.endswith("/daemons"):
            return httpx.Response(200, json=_envelope({"patched": True}))
        if request.url.path.endswith("/devices/body-error"):
            return httpx.Response(
                200, json={"success": False, "error": "operation failed"}
            )
        if request.url.path.endswith("/devices/bare-error"):
            return httpx.Response(
                200, json={"status": "error", "message": "legacy error"}
            )
        return httpx.Response(404, json={"error": "missing"})

    async def run_async():
        client = _AsyncClient(httpx.MockTransport(handler))
        try:
            assert await client.apply_parameters(
                ["d1"], ["tree"]
            ) == DeviceActionResponse(root={"applied": True})
            assert await client.patch_device_daemons(
                "d1",
                DeviceDaemonPatch(
                    {
                        "vpn": True,
                        "tracing": False,
                        "config": {"vpn": {"advertise_routes": True}},
                    }
                ),
            ) == DeviceActionResponse(root={"patched": True})
            with pytest.raises(HttpNotFoundError):
                await client.get_device("missing")
            with pytest.raises(BadRequestError, match="operation failed"):
                await client.get_device("body-error")
            with pytest.raises(BadRequestError, match="legacy error"):
                await client.get_device("bare-error")
        finally:
            await client.c.aclose()

    def run_sync():
        client = _SyncClient(httpx.MockTransport(handler))
        try:
            assert client.apply_parameters(["d1"], ["tree"]) == DeviceActionResponse(
                root={"applied": True}
            )
            assert client.patch_device_daemons(
                "d1",
                DeviceDaemonPatch(
                    {
                        "vpn": True,
                        "tracing": False,
                        "config": {"vpn": {"advertise_routes": True}},
                    }
                ),
            ) == DeviceActionResponse(root={"patched": True})
            with pytest.raises(HttpNotFoundError):
                client.get_device("missing")
            with pytest.raises(BadRequestError, match="operation failed"):
                client.get_device("body-error")
            with pytest.raises(BadRequestError, match="legacy error"):
                client.get_device("bare-error")
        finally:
            client.c.close()

    asyncio.run(run_async()) if async_mode else run_sync()
    assert requests[0].read() == b'{"device_list":["d1"],"tree_names":["tree"]}'
    assert (
        requests[1].read()
        == b'{"vpn":true,"tracing":false,"config":{"vpn":{"advertise_routes":true}}}'
    )


def test_command_model_rejects_invalid_command_and_environment_names():
    with pytest.raises(ValueError):
        DeviceCommand(cmd="")
    with pytest.raises(ValueError):
        DeviceCommand(cmd="echo", env={"NOT VALID": "value"})


def test_command_working_directory_compatibility():
    legacy = DeviceCommand(cmd="pwd", pwd="/tmp/legacy")
    assert legacy.model_dump(by_alias=True)["cwd"] == "/tmp/legacy"
    assert "pwd" not in legacy.model_dump(by_alias=True)
    preferred = DeviceCommand(cmd="pwd", pwd="/tmp/legacy", cwd="/tmp/preferred")
    assert preferred.cwd == "/tmp/preferred"


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_empty_parameter_tree_filter_applies_all_trees(async_mode):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=_envelope({}))

    if async_mode:
        client = _AsyncClient(httpx.MockTransport(respond))
        try:
            await client.apply_parameters(["device"], tree_names=[])
        finally:
            await client.c.aclose()
    else:
        client = _SyncClient(httpx.MockTransport(respond))
        try:
            client.apply_parameters(["device"], tree_names=[])
        finally:
            client.c.close()
    assert json.loads(requests[0].content) == {"device_list": ["device"]}


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_command_omits_empty_optional_strings(async_mode):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=_envelope({"jid": "job"}))

    command = DeviceCommand(cmd="pwd", cwd="", runas="", shell="")
    if async_mode:
        client = _AsyncClient(httpx.MockTransport(respond))
        try:
            await client.execute_command(["device"], command)
        finally:
            await client.c.aclose()
    else:
        client = _SyncClient(httpx.MockTransport(respond))
        try:
            client.execute_command(["device"], command)
        finally:
            client.c.close()
    assert {"cwd", "runas", "shell"}.isdisjoint(json.loads(requests[0].content))


def test_device_request_models_enforce_required_fields_and_operations_reject_dicts():
    with pytest.raises(ValueError):
        Device.model_validate({})
    with pytest.raises(ValueError):
        DeviceCreate(name="")
    with pytest.raises(ValueError):
        DeviceCreate(name="robot", python_version="invalid")
    with pytest.raises(ValueError):
        DeviceConfigVariableCreate(key="", value="x")
    with pytest.raises(ValueError):
        DeviceConfigVariableCreate(key="x", value="")
    with pytest.raises(ValueError):
        DeviceLabelCreate(key="x", value="")

    client = _SyncClient(
        httpx.MockTransport(lambda request: httpx.Response(200, json=_envelope({})))
    )
    try:
        with pytest.raises(TypeError):
            client.create_device({"name": "robot"})
        with pytest.raises(TypeError):
            client.patch_device_daemons("d1", {"vpn": True})
        with pytest.raises(TypeError):
            client.execute_command(["d1"], {"cmd": "uname"})
        with pytest.raises(TypeError):
            client.create_device_label("d1", {"key": "team", "value": "blue"})
    finally:
        client.c.close()
