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

"""Explicitly decrypt values and compose them into an offline manifest preview."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from rapyuta_io_sdk_v2 import (
    Applier,
    AsyncApplier,
    ManifestSource,
    async_decrypt_secret_file,
    decrypt_secret_file,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


async def _async_preview(manifest: Path, secret_file: Path) -> None:
    values = await async_decrypt_secret_file(secret_file)
    applier = AsyncApplier(ManifestSource(files=(manifest,), secrets=(values,)))
    result = await applier.apply(dry_run=True)
    print(f"async preview: {len(result.outcomes)} resource(s)")


def main(argv: Sequence[str] | None = None) -> int:
    """Explicitly decrypt values and preview a caller-selected manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("sync", "async"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--secret-file", type=Path, required=True)
    arguments = parser.parse_args(argv)

    if arguments.mode == "sync":
        values = decrypt_secret_file(arguments.secret_file)
        applier = Applier(
            ManifestSource(files=(arguments.manifest,), secrets=(values,))
        )
        result = applier.apply(dry_run=True)
        print(f"sync preview: {len(result.outcomes)} resource(s)")
    else:
        asyncio.run(_async_preview(arguments.manifest, arguments.secret_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
