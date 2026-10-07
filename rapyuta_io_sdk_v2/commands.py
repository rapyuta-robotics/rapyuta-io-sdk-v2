"""Utilities for waiting on asynchronous device command results."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from math import isfinite
import time
from typing import TYPE_CHECKING

from rapyuta_io_sdk_v2.context import RequestContext
from rapyuta_io_sdk_v2.models.device import DeviceCommandResponse

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.async_client import AsyncClient
    from rapyuta_io_sdk_v2.client import Client


def _validate_timing(retry_interval: float, timeout: float) -> None:
    if (
        not isfinite(retry_interval)
        or not isfinite(timeout)
        or retry_interval <= 0
        or timeout <= 0
    ):
        raise ValueError("retry_interval and timeout must be finite and positive")


def wait_for_command_result(
    client: Client,
    jid: str,
    device_ids: Sequence[str],
    *,
    retry_interval: float = 10,
    timeout: float = 300,
    context: RequestContext | None = None,
) -> DeviceCommandResponse:
    """Poll until completion or the deadline; an in-flight request can overrun it."""
    _validate_timing(retry_interval, timeout)
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"command result not available after {timeout} seconds")
        result = client.get_command_result(jid, device_ids, context=context)
        if not result.is_pending:
            return result
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"command result not available after {timeout} seconds")
        time.sleep(min(retry_interval, remaining))


async def async_wait_for_command_result(
    client: AsyncClient,
    jid: str,
    device_ids: Sequence[str],
    *,
    retry_interval: float = 10,
    timeout: float = 300,
    context: RequestContext | None = None,
) -> DeviceCommandResponse:
    """Poll until completion or the deadline; an in-flight request can overrun it."""
    _validate_timing(retry_interval, timeout)
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"command result not available after {timeout} seconds")
        result = await client.get_command_result(jid, device_ids, context=context)
        if not result.is_pending:
            return result
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"command result not available after {timeout} seconds")
        await asyncio.sleep(min(retry_interval, remaining))
