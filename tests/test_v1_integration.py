"""Configuration and client integration for the legacy service endpoints."""

import json

import httpx
import pytest

from rapyuta_io_sdk_v2 import (
    AsyncClient,
    Client,
    Configuration,
    Device,
    DeviceCreate,
    DeviceCreateResponse,
    RequestContext,
)


@pytest.mark.parametrize(
    "environment,host",
    [
        ("ga", "https://gaapiserver.apps.okd4v2.prod.rapyuta.io"),
        ("qa", "https://qaapiserver.apps.okd4v2.okd4beta.rapyuta.io"),
        ("pr123", "https://pr123apiserver.apps.okd4v2.okd4beta.rapyuta.io"),
        ("local", "http://apiserver"),
    ],
)
def test_core_host_defaults(environment, host, monkeypatch):
    monkeypatch.delenv("RIO_CORE_API_HOST", raising=False)
    monkeypatch.delenv("LOCAL_CORE_API_HOST", raising=False)
    config = Configuration(load_cli_config=False, environment=environment)
    assert config.resolved_core_api_host == host


def test_core_host_sources_and_normalization(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"core_api_host": "https://file.test/"}))
    monkeypatch.delenv("RIO_CORE_API_HOST", raising=False)
    assert Configuration(config_file=path).resolved_core_api_host == "https://file.test"
    monkeypatch.setenv("RIO_CORE_API_HOST", "https://env.test/")
    assert Configuration(config_file=path).resolved_core_api_host == "https://env.test"
    config = Configuration(config_file=path, core_api_host=" https://explicit.test/ ")
    config.environment = "qa"
    assert config.resolved_core_api_host == "https://explicit.test"
    config.core_api_host = " "
    assert config.core_api_host is None
    assert config.resolved_core_api_host.startswith("https://qaapiserver.")


def test_core_host_local_override(monkeypatch):
    monkeypatch.delenv("RIO_CORE_API_HOST", raising=False)
    monkeypatch.setenv("LOCAL_CORE_API_HOST", "http://localhost:8081")
    config = Configuration(load_cli_config=False, environment="local")
    assert config.resolved_core_api_host == "http://localhost:8081"


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
def test_clients_resolve_core_host_dynamically(client_type):
    config = Configuration(load_cli_config=False, core_api_host="https://core.test")
    # A dummy external transport avoids allocating an owned HTTP client here.
    client = client_type(config, transport=object())
    assert client.core_api_host == "https://core.test"
    config.core_api_host = "https://changed.test"
    assert client.core_api_host == "https://changed.test"


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_public_clients_share_transport_and_request_context(tmp_path, async_mode):
    source = tmp_path / "source"
    (source / "robot").mkdir(parents=True)
    (source / "robot" / "config.json").write_text('{"speed": 1}')
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.startswith("/api/paramserver/"):
            return httpx.Response(200, json={"data": {}})
        if request.url.path.endswith("/auth-keys/"):
            return httpx.Response(
                201,
                json={
                    "status": "success",
                    "response": {
                        "data": "onboard-token",
                        "device_id": "robot-id",
                        "script_command": "sudo bash start",
                    },
                },
            )
        return httpx.Response(
            200,
            json={"status": "success", "response": {"data": {"uuid": "robot-id"}}},
        )

    config = Configuration(
        load_cli_config=False,
        auth_token="token",
        project_guid="default-project",
        core_api_host="https://core.test",
        v2_api_host="https://v2.test",
    )
    context = RequestContext(project_guid="request-project", headers={"X-Trace": "test"})
    transport_type = httpx.AsyncClient if async_mode else httpx.Client
    external = transport_type(transport=httpx.MockTransport(respond))
    client = (AsyncClient if async_mode else Client)(config, transport=external)
    try:
        if async_mode:
            await client.upload_configurations(source, context=context)
            created = await client.create_device(
                DeviceCreate(name="robot"), context=context
            )
            device = await client.get_device(created.device_id, context=context)
            await client.aclose()
        else:
            client.upload_configurations(source, context=context)
            created = client.create_device(DeviceCreate(name="robot"), context=context)
            device = client.get_device(created.device_id, context=context)
            client.close()
        assert isinstance(created, DeviceCreateResponse)
        assert isinstance(device, Device)
        assert created.token == "onboard-token"
        assert not external.is_closed
        assert config.project_guid == "default-project"
        assert all(request.url.host == "core.test" for request in requests)
        assert all(
            request.headers["project"] == "request-project" for request in requests
        )
        assert all(
            request.headers["Authorization"] == "Bearer token" for request in requests
        )
        assert all(request.headers["X-Trace"] == "test" for request in requests)
    finally:
        if async_mode:
            await external.aclose()
        else:
            external.close()


def test_v1_models_are_exported_consistently():
    import rapyuta_io_sdk_v2 as sdk
    from rapyuta_io_sdk_v2 import models

    for name in (
        "Device",
        "DeviceCreate",
        "DeviceCreateResponse",
        "DeviceArch",
        "DeviceConfigVariable",
        "DeviceConfigVariableCreate",
        "DeviceConfigVariableUpdate",
        "DeviceLabel",
        "DeviceLabelCreate",
        "DeviceLabelUpdate",
        "DeviceCommand",
        "DeviceCommandResponse",
        "DeviceDaemonPatch",
        "DeviceActionResponse",
        "DeviceApplyParameters",
        "DeviceSelectionQuery",
        "ParameterNode",
        "ParameterBlob",
        "ParameterBlobList",
    ):
        assert getattr(sdk, name) is getattr(models, name)
