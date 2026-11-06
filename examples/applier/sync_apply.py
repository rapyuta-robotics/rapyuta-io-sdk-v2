# Copyright 2026 Rapyuta Robotics
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Apply explicit manifest paths with a caller-configured synchronous client."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from rapyuta_io_sdk_v2 import (
    Applier,
    ApplierExecutionError,
    ApplierOptions,
    ApplierResult,
    Client,
    Configuration,
    ManifestSource,
    ReadinessOptions,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def _report(result: ApplierResult) -> None:
    for outcome in result.outcomes:
        print(f"{outcome.identity.kind}: {outcome.status}")


def main(argv: Sequence[str] | None = None) -> int:
    """Parse caller-provided paths and apply them with a configured client."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--checks", type=int, default=50)
    parser.add_argument("--interval", type=float, default=6.0)
    arguments = parser.parse_args(argv)

    configuration = Configuration.from_file(str(arguments.config))
    client = Client(configuration)
    applier = Applier(
        ManifestSource(files=arguments.manifest),
        ApplierOptions(
            workers=arguments.workers,
            readiness=ReadinessOptions(
                checks=arguments.checks, interval=arguments.interval
            ),
        ),
    )
    try:
        _report(applier.apply(client))
    except ApplierExecutionError as error:
        _report(error.result)
        for outcome in error.result.outcomes:
            if outcome.failure is not None:
                print(f"{outcome.identity.kind}: {outcome.failure.category}")
        return 1
    finally:
        # Client has no public close method; release the HTTPX transport this
        # example created and owns.
        client.c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
