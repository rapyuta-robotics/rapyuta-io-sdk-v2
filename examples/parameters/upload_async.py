# Copyright 2026 Rapyuta Robotics

"""Upload immediate child directories using environment-provided credentials."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from rapyuta_io_sdk_v2 import AsyncClient, Configuration, ParameterUploadOptions
from rapyuta_io_sdk_v2.exceptions import ParameterUploadCancelled, ParameterUploadError
from rapyuta_io_sdk_v2.helpers import upload_parameters_async


def arguments() -> argparse.Namespace:
    """Parse the source, exact selection and explicit replacement/legacy flags."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", help="Directory containing Parameter tree directories"
    )
    parser.add_argument(
        "--tree",
        action="append",
        default=[],
        help="Exact tree name; repeat to select several",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete selected remote trees before creating them",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use alternating value/attribute directories",
    )
    parser.add_argument(
        "--inspect", action="store_true", help="Read each completed tree after upload"
    )
    parser.add_argument("--environment", default=os.getenv("RAPYUTA_ENVIRONMENT", "ga"))
    parser.add_argument("--core-api-host", default=os.getenv("RAPYUTA_CORE_API_HOST"))
    return parser.parse_args()


async def main() -> int:
    """Submit trees, show outcomes and release caller-owned resources."""
    args = arguments()
    config = Configuration(
        auth_token=os.getenv("RAPYUTA_AUTH_TOKEN"),
        project_guid=os.getenv("RAPYUTA_PROJECT_GUID"),
        environment=args.environment,
        core_api_host=args.core_api_host,
    )
    options = ParameterUploadOptions(
        tree_names=tuple(args.tree),
        delete_existing_trees=args.recreate,
        as_folder=not args.legacy,
    )
    client = AsyncClient(config)
    try:
        result = await upload_parameters_async(client, args.source, options=options)
        print(result.model_dump_json(indent=2))
        if args.inspect:
            for tree in result.completed_trees:
                response = await client.get_parameter_tree(tree)
                print(response.model_dump_json(by_alias=True, indent=2))
    except ParameterUploadCancelled as error:
        print(error.failure.model_dump_json(), file=sys.stderr)
        print(error.partial_result.model_dump_json(indent=2), file=sys.stderr)
        raise
    except ParameterUploadError as error:
        print(str(error), file=sys.stderr)
        print(error.partial_result.model_dump_json(indent=2), file=sys.stderr)
        return 1
    finally:
        await client.c.aclose()
        client.sync_client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
