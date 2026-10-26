# Copyright 2026 Rapyuta Robotics
"""Await explicit lifecycle/management operations with the same CLI options."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from examples.devices._configuration import configuration
from examples.devices.manage import operation, parser, report
from rapyuta_io_sdk_v2 import AsyncClient, models

if TYPE_CHECKING:
    import argparse


async def invoke(client: AsyncClient, args: argparse.Namespace) -> object:
    """Await one typed operation in the unchanged source context.

    Args:
        client: Caller-owned configured async client.
        args: Explicit operation inputs from the common parser.
    """
    if args.action == "list":
        return await client.list_devices(query=models.DeviceListQuery(name=args.name))
    method, values = operation(args)
    return await getattr(client, method)(*values)


async def main() -> None:
    """Release the transports owned by this example."""
    args = parser().parse_args()
    client = AsyncClient(configuration())
    try:
        report(await invoke(client, args), args)
    finally:
        await client.c.aclose()
        client.sync_client.close()


if __name__ == "__main__":
    asyncio.run(main())
