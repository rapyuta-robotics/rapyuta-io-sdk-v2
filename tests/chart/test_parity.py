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

"""Six recorded CLI-rendered application cases through packaged Chart facades."""

from __future__ import annotations

import copy
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

from rapyuta_io_sdk_v2 import ApplierOptions, ResourceScope
from rapyuta_io_sdk_v2.chart import AsyncChart, Chart, ChartInputs, ChartSource
from tests.apply.test_chart_parity import _difference

if TYPE_CHECKING:
    from collections.abc import Callable

FIXTURES = Path(__file__).parents[1] / "apply/fixtures/parity"
METADATA = Path(__file__).parent / "fixtures/metadata"
CASES = [
    ("postgis", "base"),
    ("postgis", "standby"),
    ("gateway", "base"),
    ("gateway", "toxiproxy"),
    ("gostproxy", "direct-ip"),
    ("gostproxy", "interface-ip"),
]
COUNTS = [2, 4, 2, 4, 3, 4]


def _merge(base: dict, changes: dict) -> dict:
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def _bundle(
    tmp_path: Path, name: str, case_id: str
) -> tuple[Path, ChartInputs, ApplierOptions, list]:
    directory = FIXTURES / name
    config = yaml.safe_load((directory / "cases.yaml").read_text())
    case = next(item for item in config["cases"] if item["id"] == case_id)
    root = tmp_path / name
    shutil.copytree(directory / "templates", root / "templates")
    shutil.copyfile(METADATA / name / "Chart.yaml", root / "Chart.yaml")
    shutil.copyfile(directory / config["base_values"], root / "values.yaml")
    values = _merge(
        yaml.safe_load((root / "values.yaml").read_text()), case["overrides"]
    )
    inputs = ChartInputs(
        values=values,
        rio=case["rio"],
        interface_resolver=lambda _project, _device: case.get("device", {}),
    )
    options = ApplierOptions(scope=ResourceScope(project_guid=case["project_guid"]))
    expected = yaml.safe_load((directory / "outputs.yaml").read_text())[case_id]
    return root, inputs, options, expected


def _assert_documents(chart: Chart | AsyncChart, expected: list, count: int) -> None:
    actual = chart.inspect().rendered_documents
    assert len(actual) == len(expected) == count
    for left, right in zip(expected, actual, strict=True):
        assert _difference(left, right.data) is None


@pytest.mark.parametrize(("name", "case_id"), CASES)
@pytest.mark.parametrize("source_kind", ["directory", "archive"])
def test_sync_packaged_cli_case(
    name: str,
    case_id: str,
    source_kind: str,
    *,
    tmp_path: Path,
    archive_bytes: Callable,
) -> None:
    root, inputs, options, expected = _bundle(tmp_path, name, case_id)
    source = _source(root, source_kind, archive_bytes)
    _assert_documents(
        Chart.load(source, inputs=inputs, options=options),
        expected,
        COUNTS[CASES.index((name, case_id))],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "case_id"), CASES)
@pytest.mark.parametrize("source_kind", ["directory", "archive"])
async def test_async_packaged_cli_case(
    name: str,
    case_id: str,
    source_kind: str,
    *,
    tmp_path: Path,
    archive_bytes: Callable,
) -> None:
    root, inputs, options, expected = _bundle(tmp_path, name, case_id)
    chart = await AsyncChart.load(
        _source(root, source_kind, archive_bytes), inputs=inputs, options=options
    )
    _assert_documents(chart, expected, COUNTS[CASES.index((name, case_id))])


def _source(root: Path, source_kind: str, archive_bytes: Callable) -> ChartSource:
    if source_kind == "directory":
        return ChartSource.from_directory(root)
    archive = root.parent / "chart.tgz"
    archive.write_bytes(archive_bytes(root))
    return ChartSource.from_archive(archive)
