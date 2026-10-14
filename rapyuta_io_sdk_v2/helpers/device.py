# Copyright 2026 Rapyuta Robotics
"""Synchronous command execution and response collection."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Unpack

from rapyuta_io_sdk_v2.exceptions import DeviceCommandError
from rapyuta_io_sdk_v2.helpers._device_command import CommandProgress
from rapyuta_io_sdk_v2.models.device_command import (
    DeviceCommandFailureStage,
    DeviceCommandPendingResponse,
)

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2 import Client
    from rapyuta_io_sdk_v2._client_options import HeaderOptions
    from rapyuta_io_sdk_v2.models.device_command import (
        DeviceCommand,
        DeviceCommandOutcome,
        DeviceCommandWaitOptions,
    )


def execute_device_command(
    client: Client,
    body: DeviceCommand,
    *,
    options: DeviceCommandWaitOptions | None = None,
    **kwargs: Unpack[HeaderOptions],
) -> DeviceCommandOutcome:
    """Submit once and collect explicit target outputs before the wait deadline.

    A started synchronous request may finish late; its valid output is retained
    in a timeout snapshot. Local expiry does not stop remote execution.

    Args:
        client: Caller-owned client and transport.
        body: Explicit command and targets; background mode is rejected.
        options: Local polling interval and waiting budget.
        **kwargs: Authentication/context header overrides.
    """
    progress = CommandProgress()
    try:
        body = progress.prepare(body, options)
        progress.stage = DeviceCommandFailureStage.SUBMISSION
        response = client.execute_device_command(
            body, request_timeout=progress.remaining(), **kwargs
        )
        progress.acknowledge(response, body)
        return _collect(client, progress, **kwargs)
    except DeviceCommandError:
        raise
    except Exception as error:
        raise progress.terminal(error) from error


def _collect(
    client: Client, progress: CommandProgress, **kwargs: Unpack[HeaderOptions]
) -> DeviceCommandOutcome:
    while progress.snapshot().missing_devices:
        progress.stage = DeviceCommandFailureStage.RETRIEVAL
        response = client.get_device_command_result(
            progress.jid,
            query=progress.query(),
            request_timeout=progress.remaining(),
            **kwargs,
        )
        if not isinstance(response, DeviceCommandPendingResponse):
            progress.merge(response.response.data)
        progress.remaining()
        if progress.snapshot().missing_devices:
            time.sleep(progress.pause())
    return progress.snapshot()
