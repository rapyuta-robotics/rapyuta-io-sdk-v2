# Copyright 2026 Rapyuta Robotics
"""Submit once and receive explicit device responses.

Local timeout does not stop remote execution. Failed submissions are never
retried automatically. Background direct acknowledgments indicate launch only.
"""

import argparse

from examples.devices._configuration import configuration
from rapyuta_io_sdk_v2 import (
    Client,
    DeviceCommand,
    DeviceCommandResultQuery,
    DeviceCommandWaitOptions,
)
from rapyuta_io_sdk_v2.exceptions import DeviceCommandError
from rapyuta_io_sdk_v2.helpers import execute_device_command


def parser() -> argparse.ArgumentParser:
    """Build common synchronous/asynchronous command options."""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--device", action="append", required=True)
    result.add_argument("--command", required=True)
    result.add_argument("--mode", choices=["immediate", "deferred"], default="deferred")
    result.add_argument("--direct", action="store_true")
    result.add_argument("--background", action="store_true", help="Direct launch only")
    result.add_argument("--jid", help="Perform a single direct lookup")
    result.add_argument("--wait-timeout", type=float, default=300)
    result.add_argument("--poll-interval", type=float, default=10)
    return result


def body(args: argparse.Namespace) -> DeviceCommand:
    """Preserve supplied command text and explicit device targets.

    Args:
        args: Parsed command arguments.
    """
    return DeviceCommand(
        device_ids=tuple(args.device),
        cmd=args.command,
        run_async=args.mode == "deferred",
        bg=args.background,
    )


def invoke(client: Client, args: argparse.Namespace) -> object:
    """Demonstrate a direct operation or the response-collecting helper.

    Args:
        client: Caller-owned configured client.
        args: Parsed command arguments.
    """
    if args.jid:
        return client.get_device_command_result(
            args.jid, query=DeviceCommandResultQuery(device_ids=tuple(args.device))
        )
    if args.direct:
        return client.execute_device_command(body(args))
    return execute_device_command(
        client,
        body(args),
        options=DeviceCommandWaitOptions(
            wait_timeout=args.wait_timeout, poll_interval=args.poll_interval
        ),
    )


def report(result: object) -> None:
    """Print typed identities and output representations, retaining empty strings.

    Args:
        result: Named envelope, workflow outcome, or workflow failure.
    """
    if isinstance(result, DeviceCommandError):
        print(result.failure)
        print(result.partial_result)
    else:
        print(result)


def main() -> None:
    """Run the command example and release its transport."""
    args = parser().parse_args()
    client = Client(configuration())
    try:
        report(invoke(client, args))
    except DeviceCommandError as error:
        report(error)
    finally:
        client.c.close()


if __name__ == "__main__":
    main()
