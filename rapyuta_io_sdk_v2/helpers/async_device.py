# Copyright 2026 Rapyuta Robotics
"""Awaited command collection with cancellable overall deadlines."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Unpack

from rapyuta_io_sdk_v2.exceptions import (
    DeviceCommandCancelled,
    DeviceCommandError,
    DeviceCommandTimeout,
)
from rapyuta_io_sdk_v2.helpers._device_command import CommandProgress
from rapyuta_io_sdk_v2.models.device_command import (
    DeviceCommandFailureStage,
    DeviceCommandPendingResponse,
)

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2 import AsyncClient
    from rapyuta_io_sdk_v2._client_options import HeaderOptions
    from rapyuta_io_sdk_v2.models.device_command import (
        DeviceCommand,
        DeviceCommandOutcome,
        DeviceCommandWaitOptions,
    )


async def execute_device_command_async(
    client: AsyncClient,
    body: DeviceCommand,
    *,
    options: DeviceCommandWaitOptions | None = None,
    **kwargs: Unpack[HeaderOptions],
) -> DeviceCommandOutcome:
    """Submit once and await all explicit device responses within a deadline.

    External cancellation remains cancellation and retains acknowledged progress.
    Local expiry/cancellation does not stop remote execution.

    Args:
        client: Caller-owned async client and transport.
        body: Explicit command/targets; background mode is rejected.
        options: Local polling interval and waiting budget.
        **kwargs: Authentication/context header overrides.
    """
    progress = CommandProgress(asyncio.get_running_loop().time)
    deadline = None
    try:
        body = progress.prepare(body, options)
        deadline = asyncio.timeout_at(progress.deadline)
        async with deadline:
            progress.stage = DeviceCommandFailureStage.SUBMISSION
            response = await client.execute_device_command(
                body, request_timeout=progress.remaining(), **kwargs
            )
            progress.acknowledge(response, body)
            return await _collect(client, progress, **kwargs)
    except asyncio.CancelledError as error:
        progress.stage = DeviceCommandFailureStage.CANCELLATION
        raise progress.error(
            DeviceCommandCancelled, "Command waiting cancelled"
        ) from error
    except DeviceCommandError:
        raise
    except Exception as error:
        if (
            isinstance(error, TimeoutError)
            and deadline is not None
            and deadline.expired()
        ):
            progress.stage = DeviceCommandFailureStage.TIMEOUT
            raise progress.error(
                DeviceCommandTimeout, "Command waiting deadline expired"
            ) from error
        raise progress.terminal(error) from error


async def _collect(
    client: AsyncClient, progress: CommandProgress, **kwargs: Unpack[HeaderOptions]
) -> DeviceCommandOutcome:
    while progress.snapshot().missing_devices:
        progress.stage = DeviceCommandFailureStage.RETRIEVAL
        response = await client.get_device_command_result(
            progress.jid,
            query=progress.query(),
            request_timeout=progress.remaining(),
            **kwargs,
        )
        if not isinstance(response, DeviceCommandPendingResponse):
            progress.merge(response.response.data)
        progress.remaining()
        if progress.snapshot().missing_devices:
            await asyncio.sleep(progress.pause())
    return progress.snapshot()
