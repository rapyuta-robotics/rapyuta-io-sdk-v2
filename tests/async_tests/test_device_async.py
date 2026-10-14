# Copyright 2026 Rapyuta Robotics
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest
from pydantic import ValidationError

from rapyuta_io_sdk_v2 import Daemon, DeviceDaemonReport, DeviceVPNUpdate
from tests.data.device_data import (
    BASE,
    CASES,
    DEVICE,
    VPN,
    VPN_INVALID_BODIES,
    VPN_WIRE_CASES,
    success,
)
from tests.device_contract_support import arguments, verify_request

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2 import AsyncClient
    from tests.data.device_data import DeviceCase


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
async def test_device_contract(async_client: AsyncClient, case: DeviceCase) -> None:
    async_client.config.hosts["core_api_host"] = "https://selected-core"
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return verify_request(request, case)

    await async_client.c.aclose()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        async_client.c = transport
        args, kwargs = arguments(case)
        result = await getattr(async_client, case.name)(
            *args, project_guid="source-override", **kwargs
        )
        assert len(calls) == 1
        assert calls[0].url.host == "selected-core"
        assert calls[0].headers["project"] == "source-override"
        assert calls[0].headers["organizationguid"] == "mock_org_guid"
        assert result.model_dump(
            mode="json", by_alias=True, exclude_unset=True
        ) == json.loads(case.response)
        if case.name in {"list_devices", "get_device", "update_device"}:
            data = result.response.data
            device = data[0] if case.name == "list_devices" else data
            assert isinstance(device.daemon_status, DeviceDaemonReport)
            assert device.daemon_status.root == DEVICE["daemons_status"]
            assert "daemons_status" not in device.model_extra
        assert async_client.config.project_guid == "mock_project_guid"


@pytest.mark.asyncio
@pytest.mark.parametrize("case", VPN_WIRE_CASES)
async def test_vpn_exact_wire_contract(
    async_client: AsyncClient, case: tuple[str, str]
) -> None:
    calls: list[httpx.Request] = []

    def acknowledge(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "PATCH"
        assert request.url.path == BASE + "/devices/device-a/daemons"
        assert json.loads(request.content) == json.loads(case[1])
        assert request.headers["project"] == "source-override"
        return httpx.Response(200, content=success(VPN))

    body = DeviceVPNUpdate.model_validate_json(case[0])
    original = body.model_dump()
    await async_client.c.aclose()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(acknowledge)
    ) as transport:
        async_client.c = transport
        result = await async_client.set_device_vpn(
            "device-a", body, project_guid="source-override"
        )
        assert len(calls) == 1
        assert isinstance(result.response.data, Daemon)
        assert result.response.data.kind == "DeviceDaemon"
        assert (
            result.model_dump(mode="json", by_alias=True, exclude_unset=True)[
                "response"
            ]["data"]
            == VPN
        )
        assert body.model_dump() == original
        assert async_client.config.project_guid == "mock_project_guid"
    async_client.sync_client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", VPN_INVALID_BODIES)
async def test_vpn_invalid_body_rejected_before_http(
    async_client: AsyncClient, payload: str
) -> None:
    calls: list[httpx.Request] = []

    def unexpected(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        message = "Invalid VPN payload must not reach HTTP"
        raise AssertionError(message)

    await async_client.c.aclose()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(unexpected)
    ) as transport:
        async_client.c = transport
        with pytest.raises(ValidationError):
            await _invoke_vpn(async_client, payload)
        assert not calls
    async_client.sync_client.close()


async def _invoke_vpn(client: AsyncClient, payload: str) -> None:
    await client.set_device_vpn(
        "device-a", DeviceVPNUpdate.model_validate_json(payload)
    )
