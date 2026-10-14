# Copyright 2026 Rapyuta Robotics
"""Collect command responses with cancellable asynchronous waiting.

Cancellation preserves local progress and does not cancel remote execution.
"""

import argparse
import asyncio

from examples.devices._configuration import configuration
from examples.devices.command import body, report
from examples.devices.command import parser as common_parser
from rapyuta_io_sdk_v2 import (
    AsyncClient,
    DeviceCommandResultQuery,
    DeviceCommandWaitOptions,
)
from rapyuta_io_sdk_v2.exceptions import DeviceCommandCancelled, DeviceCommandError
from rapyuta_io_sdk_v2.helpers import execute_device_command_async


def parser() -> argparse.ArgumentParser:
    """Add cancellation demonstration options to the common flags."""
    result = common_parser()
    result.add_argument("--cancel-after", type=float)
    return result


async def invoke(client: AsyncClient, args: argparse.Namespace) -> object:
    """Perform one direct awaited operation or collect responses.

    Args:
        client: Caller-owned configured async client.
        args: Parsed explicit command options.
    """
    if args.jid:
        return await client.get_device_command_result(
            args.jid, query=DeviceCommandResultQuery(device_ids=tuple(args.device))
        )
    if args.direct:
        return await client.execute_device_command(body(args))
    return await execute_device_command_async(
        client,
        body(args),
        options=DeviceCommandWaitOptions(
            wait_timeout=args.wait_timeout, poll_interval=args.poll_interval
        ),
    )


async def main() -> None:
    """Inspect and re-raise cancellation, then close owned transports."""
    args = parser().parse_args()
    client = AsyncClient(configuration())
    task = asyncio.create_task(invoke(client, args))
    timer = None
    if args.cancel_after is not None:
        timer = asyncio.get_running_loop().call_later(args.cancel_after, task.cancel)
    try:
        report(await task)
    except DeviceCommandCancelled as error:
        print(error.failure)
        print(error.partial_result)
        raise
    except DeviceCommandError as error:
        report(error)
    finally:
        if timer is not None:
            timer.cancel()
        await client.c.aclose()
        client.sync_client.close()


if __name__ == "__main__":
    asyncio.run(main())
