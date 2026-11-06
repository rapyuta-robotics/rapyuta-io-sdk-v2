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

"""Offline metadata and replay checks for the CLI fixture capture tool."""

import importlib
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from scripts import capture_apply_parity as capture

VERSIONS = {
    "python": "3.13.9",
    "ansible": "2.21.5",
    "jinja": "3.1.6",
    "cli_version": "10.10.0",
    "cli_revision": "cli-fixture-revision",
    "chart_revision": "chart-fixture-revision",
}


class StubParser:
    """Parse fixture YAML and reproduce a deterministic CLI failure."""

    def _load_manifests(self, path: str) -> list[dict]:
        text = Path(path).read_text()
        if "FAIL" in text:
            msg = f"Error rendering template {path}: synthetic failure"
            raise ValueError(msg)
        return [item for item in yaml.safe_load_all(text) if item is not None]


def _setup_direct(root: Path, suite: str) -> None:
    directory = root / suite
    directory.mkdir()
    cases = [{"id": "success", "manifest": "kind: Role\nmetadata:\n  name: ok\n"}]
    if suite == "rio-filters":
        cases.append({"id": "failure", "manifest": "FAIL\n", "expected_error": True})
    (directory / "cases.yaml").write_text(yaml.safe_dump({"cases": cases}))


def _setup_charts(root: Path, chart_root: Path) -> None:
    for chart in capture.CHARTS:
        directory = root / chart
        directory.mkdir()
        source = chart_root / "incubator" / chart
        (source / "templates").mkdir(parents=True)
        (source / "templates" / "role.yaml").write_text(
            "kind: Role\nmetadata:\n  name: chart-role\n"
        )
        (source / "values.yaml").write_text("name: test\n")
        (directory / "cases.yaml").write_text(
            yaml.safe_dump(
                {
                    "base_values": "values.yaml",
                    "cases": [{"id": "base", "overrides": {}}],
                }
            )
        )


@pytest.fixture
def stub_capture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    output = tmp_path / "output"
    output.mkdir()
    chart_root = tmp_path / "charts"
    _setup_direct(output, "rio-filters")
    _setup_direct(output, "ansible-filters")
    _setup_charts(output, chart_root)
    monkeypatch.setattr(capture, "_metadata", lambda *_args: VERSIONS.copy())
    monkeypatch.setattr(capture, "_cli_parser", lambda *_args: StubParser())
    monkeypatch.setattr(capture, "_case_inputs", lambda _case: nullcontext())
    monkeypatch.setattr(
        capture,
        "_git",
        lambda _root, *args: args[-1] if "--error-unmatch" in args else "revision",
    )
    monkeypatch.setattr(
        capture,
        "_tracked_chart_sources",
        lambda root, chart: [root / "incubator" / chart / "templates" / "role.yaml"],
    )
    for suite in ("rio-filters", "ansible-filters"):
        capture._direct_suite(suite, output, tmp_path, write=True)  # noqa: SLF001 - fixture setup
    capture._chart_suite(output, tmp_path, chart_root, write=True)  # noqa: SLF001 - fixture setup
    return output, chart_root


@pytest.mark.parametrize("field", ["python", "ansible", "jinja", "cli_revision"])
def test_version_drift_rejected_before_parser_or_writes(
    stub_capture: tuple[Path, Path], field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, _chart_root = stub_capture
    before = {p: p.read_bytes() for p in output.rglob("*") if p.is_file()}
    changed = VERSIONS | {field: "different"}
    monkeypatch.setattr(capture, "_metadata", lambda *_args: changed)

    def unexpected(_root: Path) -> None:
        msg = "parser initialized despite version drift"
        raise AssertionError(msg)

    monkeypatch.setattr(capture, "_cli_parser", unexpected)
    with pytest.raises(ValueError, match=f"{field} drift"):
        capture._direct_suite("rio-filters", output, output, write=False)  # noqa: SLF001 - replay gate
    assert {p: p.read_bytes() for p in before} == before


def test_matching_metadata_replays_all_suites_without_writes(
    stub_capture: tuple[Path, Path],
) -> None:
    output, chart_root = stub_capture
    before = {p: p.read_bytes() for p in output.rglob("*") if p.is_file()}
    capture._direct_suite("rio-filters", output, output, write=False)  # noqa: SLF001 - replay gate
    capture._direct_suite("ansible-filters", output, output, write=False)  # noqa: SLF001 - replay gate
    capture._chart_suite(output, output, chart_root, write=False)  # noqa: SLF001 - replay gate
    assert {p: p.read_bytes() for p in before} == before
    errors = json.loads((output / "rio-filters" / "errors.json").read_text())
    assert errors == [
        {
            "id": "failure",
            "type": "ValueError",
            "message": (
                "Error rendering template manifests/failure.yaml: synthetic failure"
            ),
        }
    ]


def _fake_cli(root: Path, marker: str) -> None:
    package = root / "riocli"
    apply = package / "apply"
    apply.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (apply / "__init__.py").write_text("")
    (apply / "parse.py").write_text("class Applier: pass\n")
    (apply / "util.py").write_text(f"def init_jinja_environment(): return {marker!r}\n")
    (apply / "filters.py").write_text(
        "def get_device_ip_interfaces(_name): raise AssertionError('live lookup')\n"
    )


@contextmanager
def _isolated_cli_imports() -> Iterator[None]:
    original_path = sys.path.copy()
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "riocli" or name.startswith("riocli.")
    }
    try:
        for name in saved:
            sys.modules.pop(name)
        yield
    finally:
        for name in tuple(sys.modules):
            if name == "riocli" or name.startswith("riocli."):
                sys.modules.pop(name)
        sys.modules.update(saved)
        sys.path[:] = original_path


def test_selected_cli_checkout_precedes_ambient_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ambient = tmp_path / "ambient"
    selected = tmp_path / "selected"
    _fake_cli(ambient, "ambient")
    _fake_cli(selected, "selected")
    with _isolated_cli_imports():
        monkeypatch.syspath_prepend(str(ambient))
        parser = capture._cli_parser(selected)  # noqa: SLF001 - import provenance gate
        assert parser.environment == "selected"
        with capture._case_inputs({"device": {"eth0": ["192.0.2.1"]}}):  # noqa: SLF001 - selected filters
            filters = importlib.import_module("riocli.apply.filters")

            assert filters.get_device_ip_interfaces("device") == {"eth0": ["192.0.2.1"]}
            assert Path(filters.__file__).is_relative_to(selected)


def test_loaded_ambient_cli_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ambient = tmp_path / "ambient"
    selected = tmp_path / "selected"
    _fake_cli(ambient, "ambient")
    _fake_cli(selected, "selected")
    with _isolated_cli_imports():
        monkeypatch.syspath_prepend(str(ambient))
        __import__("riocli.apply.parse")
        with pytest.raises(RuntimeError, match="outside --cli-root"):
            capture._cli_parser(selected)  # noqa: SLF001 - import provenance gate


def test_cli_revision_comes_from_selected_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = tmp_path / "selected"
    _fake_cli(selected, "selected")
    (selected / "riocli" / "bootstrap.py").write_text('__version__ = "42.0"\n')
    monkeypatch.setattr(capture, "version", lambda name: name)
    monkeypatch.setattr(
        capture,
        "_git",
        lambda root, *_args: "selected-revision" if root == selected else "other",
    )
    metadata = capture._metadata(selected)  # noqa: SLF001 - provenance gate
    assert metadata["cli_revision"] == "selected-revision"
    assert metadata["cli_version"] == "42.0"


def test_missing_device_response_fails_locally(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    filters = ModuleType("riocli.apply.filters")
    calls = []

    def live_provider(name: str) -> dict:
        calls.append(name)
        return {}

    filters.get_device_ip_interfaces = live_provider

    def get_interface_ip(name: str, interface: str) -> str:
        return filters.get_device_ip_interfaces(name)[interface][0]

    filters.get_interface_ip = get_interface_ip
    apply = ModuleType("riocli.apply")
    apply.filters = filters
    monkeypatch.setitem(sys.modules, "riocli", ModuleType("riocli"))
    monkeypatch.setitem(sys.modules, "riocli.apply", apply)
    monkeypatch.setitem(sys.modules, "riocli.apply.filters", filters)
    manifest = tmp_path / "device.yaml"
    manifest.write_text("ip: {{ 'robot' | get_intf_ip('eth0') }}\n")

    class DeviceParser:
        def _load_manifests(self, path: str) -> list[dict]:
            assert "get_intf_ip('eth0')" in Path(path).read_text()
            return [{"ip": filters.get_interface_ip("robot", "eth0")}]

    with pytest.raises(RuntimeError, match="controlled device response"):
        capture._parse_case(  # noqa: SLF001 - offline capture gate
            DeviceParser(), {"id": "missing"}, [manifest], values={}
        )
    assert calls == []
    assert capture._parse_case(  # noqa: SLF001 - controlled case gate
        DeviceParser(),
        {"id": "controlled", "device": {"eth0": ["192.0.2.1"]}},
        [manifest],
        values={},
    ) == [{"ip": "192.0.2.1"}]
    assert calls == []
    assert filters.get_device_ip_interfaces is live_provider


@pytest.mark.parametrize(
    ("field", "replacement"),
    [("flag", 1), ("count", 1.0), ("order", ["second", "first"])],
)
def test_typed_output_drift_rejected_without_writes(
    stub_capture: tuple[Path, Path], field: str, replacement: object
) -> None:
    output, _chart_root = stub_capture
    directory = output / "rio-filters"
    cases_path = directory / "cases.yaml"
    cases = yaml.safe_load(cases_path.read_text())
    cases["cases"][0]["manifest"] = (
        "kind: Role\nflag: true\ncount: 1\norder: [first, second]\n"
    )
    cases_path.write_text(yaml.safe_dump(cases))
    (directory / "manifests" / "success.yaml").write_text(cases["cases"][0]["manifest"])
    expected = capture._direct_cases(  # noqa: SLF001 - expected output setup
        StubParser(), cases["cases"], directory, write=False
    )[0]
    expected["success"][0][field] = replacement
    (directory / "outputs.yaml").write_text(yaml.safe_dump(expected))
    sources = {
        "cases.yaml": capture._sha(cases_path.read_bytes()),  # noqa: SLF001 - provenance setup
        **{
            case["id"]: capture._sha(case["manifest"].encode())  # noqa: SLF001 - provenance setup
            for case in cases["cases"]
        },
    }
    provenance = json.loads((directory / "provenance.json").read_text())
    provenance["sources"] = sources
    (directory / "provenance.json").write_text(json.dumps(provenance))
    before = {p: p.read_bytes() for p in output.rglob("*") if p.is_file()}

    with pytest.raises(ValueError, match="CLI output drift"):
        capture._direct_suite("rio-filters", output, output, write=False)  # noqa: SLF001 - replay gate
    assert {p: p.read_bytes() for p in before} == before


def test_mapping_keys_are_type_sensitive() -> None:
    assert not capture._typed_equal({True: "same"}, {1: "same"})  # noqa: SLF001 - recursive comparison gate


def test_chart_refresh_removes_obsolete_template_copies(
    stub_capture: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    output, chart_root = stub_capture
    copied_templates = output / "postgis" / "templates"
    obsolete = copied_templates / "obsolete.yaml"
    obsolete.write_text("kind: Role\nmetadata:\n  name: obsolete\n")
    before = {path: path.read_bytes() for path in output.rglob("*") if path.is_file()}
    with pytest.raises(ValueError, match="unexpected copied chart template"):
        capture._chart_suite(output, output, chart_root, write=False)  # noqa: SLF001 - stale-copy gate
    assert {path: path.read_bytes() for path in before} == before

    upstream = chart_root / "incubator" / "postgis" / "templates"
    (upstream / "role.yaml").rename(upstream / "renamed.yaml")

    def tracked(root: Path, chart: str) -> list[Path]:
        name = "renamed.yaml" if chart == "postgis" else "role.yaml"
        return [root / "incubator" / chart / "templates" / name]

    monkeypatch.setattr(capture, "_tracked_chart_sources", tracked)
    capture._chart_suite(output, output, chart_root, write=True)  # noqa: SLF001 - refresh gate
    assert not obsolete.exists()
    assert not (copied_templates / "role.yaml").exists()
    assert (copied_templates / "renamed.yaml").is_file()
    capture._chart_suite(output, output, chart_root, write=False)  # noqa: SLF001 - replay gate
