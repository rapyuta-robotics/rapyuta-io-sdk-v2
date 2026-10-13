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

"""Type sensitive chart rendering parity against checked in CLI output."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from rapyuta_io_sdk_v2 import (
    Applier,
    ApplierOptions,
    AsyncApplier,
    ManifestSource,
    ResourceScope,
)
from rapyuta_io_sdk_v2.async_client import AsyncClient
from rapyuta_io_sdk_v2.client import Client

FIXTURES = Path(__file__).parent / "fixtures" / "parity"
COUNTS = {
    ("postgis", "base"): 2,
    ("postgis", "standby"): 4,
    ("gateway", "base"): 2,
    ("gateway", "toxiproxy"): 4,
    ("gostproxy", "direct-ip"): 3,
    ("gostproxy", "interface-ip"): 4,
}


def _merge(base: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = deepcopy(value)
    return base


def _mapping_difference(expected: dict, actual: dict, path: str) -> str | None:
    if len(expected) != len(actual):
        return f"{path}: {len(expected)} keys != {len(actual)} keys"
    for key, value in expected.items():
        matches = [
            candidate
            for candidate in actual
            if type(candidate) is type(key) and candidate == key
        ]
        if not matches:
            return f"{path}[{key!r}]: missing key or key type drift"
        result = _difference(value, actual[matches[0]], f"{path}.{key}")
        if result:
            return result
    return None


def _list_difference(expected: list, actual: list, path: str) -> str | None:
    if len(expected) != len(actual):
        return f"{path}: length {len(expected)} != {len(actual)}"
    for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
        result = _difference(left, right, f"{path}[{index}]")
        if result:
            return result
    return None


def _difference(expected: object, actual: object, path: str = "$") -> str | None:
    if type(expected) is not type(actual):
        return f"{path}: {type(expected).__name__} != {type(actual).__name__}"
    if isinstance(expected, dict):
        return _mapping_difference(expected, actual, path)
    if isinstance(expected, list):
        return _list_difference(expected, actual, path)
    return f"{path}: {expected!r} != {actual!r}" if expected != actual else None


@pytest.mark.parametrize(
    ("expected", "actual", "path"),
    [
        ({True: "same"}, {1: "same"}, "$[True]"),
        ({1: "same"}, {1.0: "same"}, "$[1]"),
        ({"value": 1}, {"value": True}, "$.value"),
        ({"items": ["first", "second"]}, {"items": ["second", "first"]}, "$.items[0]"),
        (
            [{"id": "first"}, {"id": "second"}],
            [{"id": "second"}, {"id": "first"}],
            "$[0].id",
        ),
    ],
)
def test_recursive_parity_difference_reports_type_and_order_drift(
    expected: object, actual: object, path: str
) -> None:
    difference = _difference(expected, actual)
    assert difference is not None
    assert path in difference


def test_recursive_parity_difference_ignores_mapping_order() -> None:
    assert _difference({"first": 1, "second": 2}, {"second": 2, "first": 1}) is None


@pytest.mark.parametrize("facade", [Applier, AsyncApplier])
@pytest.mark.parametrize(("chart", "case_id"), COUNTS)
def test_chart_cli_parity(
    chart: str, case_id: str, facade: type, *, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected(*_args: object, **_kwargs: object) -> None:
        msg = "chart rendering attempted platform access"
        raise AssertionError(msg)

    monkeypatch.setattr(Client, "__init__", unexpected)
    monkeypatch.setattr(AsyncClient, "__init__", unexpected)
    directory = FIXTURES / chart
    config = yaml.safe_load((directory / "cases.yaml").read_text())
    case = next(item for item in config["cases"] if item["id"] == case_id)
    base = yaml.safe_load((directory / config["base_values"]).read_text())
    values = _merge(base, case["overrides"])
    expected = yaml.safe_load((directory / "outputs.yaml").read_text())[case_id]
    source = ManifestSource(
        files=tuple(sorted((directory / "templates").glob("*.yaml"))),
        values=(values,),
        rio=case["rio"],
        interface_resolver=lambda _project, _device: case.get("device", {}),
    )
    options = ApplierOptions(scope=ResourceScope(project_guid=case["project_guid"]))
    actual = facade(source, options).inspect().rendered_documents
    assert len(expected) == len(actual) == COUNTS[(chart, case_id)]
    for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
        mismatch = _difference(left, right.data)
        assert mismatch is None, f"{chart}/{case_id} document {index}: {mismatch}"
