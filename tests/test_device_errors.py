# Copyright 2026 Rapyuta Robotics
"""Paired service refusals and request ownership for every Device operation."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

import httpx
import pytest

from rapyuta_io_sdk_v2 import exceptions
from tests.data.device_data import CASES, COMMAND_REFUSALS
from tests.device_contract_support import arguments

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2 import AsyncClient, Client
    from tests.data.device_data import DeviceCase


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
@pytest.mark.parametrize("failure", COMMAND_REFUSALS)
async def test_service_refusal_is_terminal(
    *,
    mode: str,
    case: DeviceCase,
    failure: tuple[int, str],
    client: Client,
    async_client: AsyncClient,
) -> None:
    status, payload = failure
    target = client if mode == "sync" else async_client
    original = target.c.timeout
    calls: list[httpx.Request] = []

    def refusal(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            status,
            content=payload,
        )

    if mode == "sync":
        target.c.close()
        target.c = httpx.Client(
            transport=httpx.MockTransport(refusal), timeout=original
        )
    else:
        await target.c.aclose()
        target.c = httpx.AsyncClient(
            transport=httpx.MockTransport(refusal), timeout=original
        )
    category = {
        400: exceptions.MethodNotAllowedError,
        401: exceptions.UnauthorizedAccessError,
        403: exceptions.MethodNotAllowedError,
        404: exceptions.HttpNotFoundError,
        429: exceptions.UnknownError,
    }[status]
    try:
        with pytest.raises(category, match="Device offline"):
            await _invoke(target, case)
        assert len(calls) == 1
        assert target.c.timeout == original
        assert not target.c.is_closed
        assert target.config.project_guid == "mock_project_guid"
    finally:
        if mode == "sync":
            target.c.close()
        else:
            await target.c.aclose()
            target.sync_client.close()


async def _invoke(target: Client | AsyncClient, case: DeviceCase) -> None:
    args, kwargs = arguments(case)
    result = getattr(target, case.name)(*args, **kwargs)
    if inspect.isawaitable(result):
        await result
