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

"""Capture replay gates validate provenance before invoking the CLI oracle."""

import os
import socket
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from scripts import capture_apply_parity
from scripts import chart_workflow_oracle as oracle
from scripts.capture_apply_parity import _check_cli_modules, _sha
from scripts.chart_workflow_oracle import (
    _forward,
    _modules,
    _offline_requests,
    _recreation,
)


@pytest.fixture
def workflow_capture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple:
    output = tmp_path / "workflows"
    output.mkdir()
    (tmp_path / "metadata").mkdir()
    (tmp_path / "metadata/provenance.json").write_text("{}")
    (output / "cases.yaml").write_text("index: {}")
    cli = tmp_path / "cli"
    for name in [
        "chart/util.py",
        "chart/chart.py",
        "chart/apply.py",
        "apply/__init__.py",
    ]:
        path = cli / "riocli" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("controlled source")
    calls = []
    versions = {"cli_revision": "recorded", "python": "recorded"}
    monkeypatch.setattr(
        capture_apply_parity, "_metadata", lambda _root: versions.copy()
    )
    monkeypatch.setattr(
        oracle,
        "_capture",
        lambda *_args: calls.append("capture") or {"result": "reference"},
    )
    oracle.capture_workflows(output, cli, write=True)
    return output, cli, versions, calls


@pytest.mark.parametrize(
    "drift",
    ["cases", "cli_source", "metadata", "oracle_source", "environment", "revision"],
)
def test_workflow_replay_drift_stops_before_oracle(
    workflow_capture: tuple,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    output, cli, versions, calls = workflow_capture
    before = {
        name: (output / name).read_bytes()
        for name in ["outputs.yaml", "provenance.json"]
    }
    oracle.capture_workflows(output, cli, write=False)
    assert before == {name: (output / name).read_bytes() for name in before}
    _change_capture_input(
        output, cli, drift, versions=versions, monkeypatch=monkeypatch
    )
    prior = list(calls)
    with pytest.raises(ValueError, match="drift"):
        oracle.capture_workflows(output, cli, write=False)
    assert calls == prior
    assert before == {name: (output / name).read_bytes() for name in before}


def _change_capture_input(
    output: Path,
    cli: Path,
    drift: str,
    *,
    versions: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _sha
    oracle_bytes = Path(oracle.__file__).read_bytes()
    mutations = {
        "cases": lambda: (output / "cases.yaml").write_text("index: {changed: true}"),
        "cli_source": lambda: (cli / "riocli/chart/util.py").write_text("changed"),
        "metadata": lambda: (output.parent / "metadata/provenance.json").write_text(
            '{"changed": true}'
        ),
        "environment": lambda: versions.update(python="changed"),
        "revision": lambda: versions.update(cli_revision="changed"),
        "oracle_source": lambda: monkeypatch.setattr(
            capture_apply_parity,
            "_sha",
            lambda data: "changed" if data == oracle_bytes else original(data),
        ),
    }
    mutations[drift]()


def test_oracle_blocks_socket_connections() -> None:
    with (
        _offline_requests(),
        socket.socket() as connection,
        pytest.raises(AssertionError, match="network"),
    ):
        connection.connect(("127.0.0.1", 1))


def test_forwarding_layer_invokes_chart_method_and_records_callback() -> None:
    module = SimpleNamespace(
        apply=SimpleNamespace(callback=lambda **_kwargs: None),
        delete=SimpleNamespace(callback=lambda **_kwargs: None),
    )
    invoked = []

    class ChartProtocol:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def apply_chart(self, **kwargs: object) -> None:
            invoked.append("chart")
            module.apply.callback(files=["/chart-root/sample/templates"], **kwargs)

    module.Chart = ChartProtocol
    case = {
        "id": "explicit",
        "operation": "apply",
        "values": ["first.yaml", "second.yaml"],
        "secrets": ["secret.yaml"],
        "dryrun": True,
    }
    result = _forward(module, case)
    assert invoked == ["chart"]
    assert result["values"] == case["values"]
    assert result["secrets"] == case["secrets"]
    assert result["files"] == ["templates"]


@pytest.mark.parametrize("fail", [False, True])
def test_recreation_layer_keeps_original_callback_and_short_circuits_delete(
    *,
    fail: bool,
) -> None:
    module = _apply_protocol()
    callback = module.apply.callback
    result = _recreation(
        module, {"fail_delete": fail, "dryrun": False, "recreate": True}
    )
    assert module.apply.callback is callback
    assert [event["operation"] for event in result["events"]] == (
        ["delete"] if fail else ["delete", "apply"]
    )
    assert result["failed"] == fail
    assert module.invoked == ["original apply callback"]


def _apply_protocol() -> object:
    module = SimpleNamespace(
        invoked=[],
        Applier=None,
        get_config_from_context=lambda: None,
        print_context=lambda: None,
        print_centered_text=lambda: None,
        process_files_values_secrets=lambda: None,
        click=SimpleNamespace(Context=lambda _command: nullcontext()),
    )

    def callback(**kwargs: object) -> None:
        module.invoked.append("original apply callback")
        engine = module.Applier()
        options = {
            key: kwargs[key]
            for key in ["workers", "retry_count", "retry_interval", "dryrun"]
        }
        if kwargs["delete_existing"]:
            engine.delete(**options)
        engine.apply(**options)

    module.apply = SimpleNamespace(callback=callback)
    return module


def test_ambient_cli_checkout_is_rejected_before_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = ModuleType("riocli")
    module.__file__ = str(tmp_path / "ambient/riocli/__init__.py")
    monkeypatch.setitem(sys.modules, "riocli", module)
    with pytest.raises(RuntimeError, match="outside --cli-root"):
        _check_cli_modules(tmp_path / "selected")


@pytest.mark.parametrize(
    "suite", [None, "chart-workflows", "charts", "rio-filters", "ansible-filters"]
)
def test_original_capture_suite_dispatch_is_preserved(
    monkeypatch: pytest.MonkeyPatch, suite: str | None
) -> None:
    calls = []
    monkeypatch.setattr(
        capture_apply_parity,
        "capture_workflows",
        lambda *_args, **_kwargs: calls.append("chart-workflows"),
    )
    monkeypatch.setattr(
        capture_apply_parity,
        "_chart_suite",
        lambda *_args, **_kwargs: calls.append("charts"),
    )
    monkeypatch.setattr(
        capture_apply_parity,
        "_direct_suite",
        lambda name, *_args, **_kwargs: calls.append(name),
    )
    capture_apply_parity.main(["--verify", *(["--suite", suite] if suite else [])])
    assert calls == ([suite] if suite else ["rio-filters", "ansible-filters", "charts"])


def test_oracle_imports_only_the_selected_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = tmp_path / "selected"
    for relative in [
        "riocli/__init__.py",
        "riocli/chart/__init__.py",
        "riocli/chart/util.py",
        "riocli/chart/chart.py",
        "riocli/apply/__init__.py",
        "riocli/apply/parse.py",
    ]:
        path = selected / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("selected = True\n")
    monkeypatch.setattr(sys, "path", list(sys.path))
    before = set(sys.modules)
    try:
        modules = _modules(selected)
        assert all(module.selected for module in modules)
        assert all(Path(module.__file__).is_relative_to(selected) for module in modules)
    finally:
        for name in set(sys.modules) - before:
            if name == "riocli" or name.startswith("riocli."):
                sys.modules.pop(name)


@pytest.mark.parametrize("mode", ["script", "module"])
@pytest.mark.parametrize("action", ["help", "workflow"])
def test_capture_entrypoints_without_pythonpath(
    tmp_path: Path, mode: str, action: str
) -> None:
    root = Path(__file__).resolve().parents[2]
    command = (
        [sys.executable, "-I", str(root / "scripts/capture_apply_parity.py")]
        if mode == "script"
        else [sys.executable, "-m", "scripts.capture_apply_parity"]
    )
    arguments = (
        ["--help"]
        if action == "help"
        else [
            "--suite",
            "chart-workflows",
            "--verify",
            "--cli-root",
            str(tmp_path / "missing-cli"),
            "--output",
            str(root / "tests/chart/fixtures/workflows"),
        ]
    )
    result = subprocess.run(  # noqa: S603 - fixed interpreter and controlled script arguments
        [*command, *arguments],
        cwd=tmp_path if mode == "script" else root,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if action == "help":
        assert result.returncode == 0, result.stderr
        assert "chart-workflows" in result.stdout
    else:
        assert result.returncode != 0
        assert "rio CLI parser unavailable" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
