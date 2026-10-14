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

"""Inspect, preview, or explicitly execute a selected chart synchronously."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from rapyuta_io_sdk_v2 import Client, Configuration, decrypt_secret_file
from rapyuta_io_sdk_v2.apply.errors import ApplierError
from rapyuta_io_sdk_v2.chart import Chart, ChartError, ChartInputs, ChartSource

if TYPE_CHECKING:
    from collections.abc import Sequence


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--directory", type=Path)
    sources.add_argument("--archive", type=Path)
    sources.add_argument("--chart")
    parser.add_argument("--repository")
    parser.add_argument("--branch")
    parser.add_argument("--values", action="append", type=Path, default=[])
    parser.add_argument("--secrets", action="append", type=Path, default=[])
    parser.add_argument("--encrypted-secrets", action="append", type=Path, default=[])
    parser.add_argument("--rio", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--action", choices=["inspect", "apply", "delete"], default="inspect"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delete-existing", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.action != "inspect" and not (arguments.dry_run or arguments.config):
        parser.error("live actions require --config; preview with --dry-run")
    return arguments


def _source(arguments: argparse.Namespace) -> ChartSource:
    if arguments.directory:
        return ChartSource.from_directory(arguments.directory)
    if arguments.archive:
        return ChartSource.from_archive(arguments.archive)
    return ChartSource.from_repository(
        arguments.chart, repository=arguments.repository, branch=arguments.branch
    )


def _inputs(arguments: argparse.Namespace) -> ChartInputs:
    secrets = list(arguments.secrets)
    secrets.extend(decrypt_secret_file(path) for path in arguments.encrypted_secrets)
    rio = yaml.safe_load(arguments.rio.read_text()) if arguments.rio else None
    return ChartInputs(values=arguments.values, secrets=secrets, rio=rio)


def _execute(chart: Chart, arguments: argparse.Namespace) -> None:
    if arguments.action == "inspect":
        print(chart.metadata.model_dump_json(indent=2))
        print(chart.inspect().model_dump_json(indent=2))
        return
    client = (
        Client(Configuration.from_file(str(arguments.config)))
        if not arguments.dry_run
        else None
    )
    try:
        if arguments.action == "apply":
            chart.apply(
                client,
                dry_run=arguments.dry_run,
                delete_existing=arguments.delete_existing,
            )
        else:
            chart.delete(client, dry_run=arguments.dry_run)
        for phase in chart.phase_results:
            print(phase.model_dump_json(indent=2))
    finally:
        if client is not None:
            # This example owns the client; the SDK has no public close API.
            client.c.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the example with explicit inputs, printing original phase failures."""
    arguments = _arguments(argv)
    chart = None
    try:
        chart = Chart.load(_source(arguments), inputs=_inputs(arguments))
        _execute(chart, arguments)
    except (ChartError, ApplierError) as error:
        print(str(error))
        if chart is not None:
            for phase in chart.phase_results:
                print(phase.model_dump_json(indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
