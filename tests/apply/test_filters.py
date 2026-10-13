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

"""Direct CLI oracle comparisons for rio and Ansible filter expressions."""

import json
from pathlib import Path

import pytest
import yaml

from rapyuta_io_sdk_v2 import (
    Applier,
    ApplierOptions,
    AsyncApplier,
    ManifestSource,
    ResourceScope,
)

FIXTURES = Path(__file__).parent / "fixtures" / "parity"


@pytest.mark.parametrize("facade", [Applier, AsyncApplier])
@pytest.mark.parametrize("suite", ["rio-filters", "ansible-filters"])
def test_direct_cli_filter_oracle(
    facade: type, suite: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = FIXTURES / suite
    cases = yaml.safe_load((directory / "cases.yaml").read_text())["cases"]
    expected = yaml.safe_load((directory / "outputs.yaml").read_text())
    for case in cases:
        if case.get("expected_error"):
            continue
        _assert_direct_case(
            case, directory, expected, facade=facade, monkeypatch=monkeypatch
        )


def _assert_direct_case(
    case: dict,
    directory: Path,
    expected: dict,
    *,
    facade: type,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_case_environment(case, monkeypatch)
    seen: list[tuple[str, str]] = []

    def resolve(project_guid: str, device_name: str) -> dict:
        seen.append((project_guid, device_name))
        return case["device"]

    source = ManifestSource(
        files=(directory / "manifests" / f"{case['id']}.yaml",),
        rio=case.get("rio"),
        interface_resolver=resolve if "device" in case else None,
    )
    options = ApplierOptions(scope=ResourceScope(project_guid=case.get("project_guid")))
    actual = facade(source, options).inspect().resolved_manifests
    assert len(actual) == len(expected[case["id"]])
    for resource, document in zip(actual, expected[case["id"]], strict=True):
        assert resource.metadata.name == document["metadata"]["name"]
        assert resource.spec.description == document["spec"]["description"]
    if "device" in case:
        assert seen == [(case["project_guid"], "edge-test")]


def _set_case_environment(case: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in case.get("env", {}).items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


def test_rio_failure_reference_identifies_device_and_interfaces() -> None:
    records = json.loads((FIXTURES / "rio-filters" / "errors.json").read_text())
    record = next(item for item in records if item["id"] == "interface-no-address")
    assert record["id"] == "interface-no-address"
    assert record["type"] == "Exception"
    assert "edge-test" in record["message"]
    assert "eth0,tailscale0" in record["message"]
    getenv = next(item for item in records if item["id"] == "getenv-invalid")
    assert getenv["type"] == "Exception"
    assert "getenv-invalid.yaml" in getenv["message"]
