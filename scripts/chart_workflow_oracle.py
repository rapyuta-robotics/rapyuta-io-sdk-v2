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

"""Explicit offline rio CLI Chart decision capture, never used by SDK runtime."""

from __future__ import annotations

import importlib
import io
import json
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

import yaml

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from types import ModuleType


def _reject_connection(*_args: object, **_kwargs: object) -> None:
    msg = "CLI oracle attempted live network access"
    raise AssertionError(msg)


@contextmanager
def _offline_requests() -> Iterator[None]:
    with (
        patch("socket.socket.connect", side_effect=_reject_connection),
        patch("socket.socket.connect_ex", side_effect=_reject_connection),
    ):
        yield


def _modules(cli_root: Path) -> tuple[ModuleType, ModuleType, ModuleType]:
    from scripts.capture_apply_parity import (  # noqa: PLC0415 - explicit CLI oracle
        _add_cli_paths,
        _check_cli_modules,
    )

    _add_cli_paths(cli_root)
    modules = tuple(
        importlib.import_module(name)
        for name in ("riocli.chart.util", "riocli.chart.chart", "riocli.apply")
    )
    _check_cli_modules(cli_root)
    return modules


def _lookup(util: ModuleType, selector: str) -> dict:
    try:
        entries = util.find_chart(selector)
    except Exception:  # noqa: BLE001 - CLI raises generic exceptions; capture boundary only
        return {"found": False}
    return {"found": bool(entries), "entries": entries or []}


def _catalog(util: ModuleType, config: dict) -> dict:
    rows = []
    with patch.object(
        util, "tabulate_data", side_effect=lambda data, _headers: rows.extend(data)
    ):
        entries = [
            entry
            for versions in config["index"]["entries"].values()
            for entry in versions
        ]
        util.print_chart_entries(entries)
    return {
        "branches": {
            branch: util.branch_repository_url(branch) for branch in config["branches"]
        },
        "default_index": util.DEFAULT_REPOSITORY,
        "lookups": {
            selector: _lookup(util, selector) for selector in config["selectors"]
        },
        "listing": [[row[0], row[1]] for row in rows],
    }


def _normalize_paths(values: object) -> list[str]:
    sequence = [values] if isinstance(values, str) else list(values)
    return [str(value).replace("/chart-root/sample/", "") for value in sequence]


def _forward(chart_module: ModuleType, case: dict) -> dict:
    recorded = {}

    def callback(**kwargs: object) -> None:
        recorded.update(kwargs)

    command = (
        chart_module.apply if case["operation"] == "apply" else chart_module.delete
    )
    chart = chart_module.Chart(
        name="sample", version="2", urls=["https://charts.example/first.tgz"]
    )
    chart.downloaded = True
    chart.tmp_dir = SimpleNamespace(name="/chart-root")
    with patch.object(command, "callback", side_effect=callback):
        method = (
            chart.apply_chart if case["operation"] == "apply" else chart.delete_chart
        )
        arguments = {
            key: value for key, value in case.items() if key not in {"id", "operation"}
        }
        method(**arguments, workers=3)
    return {
        key: _normalize_paths(value) if key in {"values", "secrets", "files"} else value
        for key, value in recorded.items()
    }


class _LifecycleRecorder:
    def __init__(self, events: list, *, fail_delete: bool) -> None:
        self.events = events
        self.fail_delete = fail_delete

    def __call__(self, *_args: object) -> _LifecycleRecorder:
        return self

    def print_summary(self) -> None:
        pass

    def apply(self, **kwargs: object) -> None:
        self.events.append({"operation": "apply", **kwargs})

    def delete(self, **kwargs: object) -> None:
        self.events.append({"operation": "delete", **kwargs})
        if self.fail_delete:
            msg = "controlled CLI deletion failure"
            raise RuntimeError(msg)


def _recreation(apply_module: ModuleType, case: dict) -> dict:
    events = []
    recorder = _LifecycleRecorder(events, fail_delete=case["fail_delete"])
    with ExitStack() as stack:
        stack.enter_context(patch.object(apply_module, "Applier", recorder))
        stack.enter_context(
            patch.object(apply_module, "get_config_from_context", return_value=object())
        )
        stack.enter_context(patch.object(apply_module, "print_context"))
        stack.enter_context(patch.object(apply_module, "print_centered_text"))
        stack.enter_context(
            patch.object(
                apply_module,
                "process_files_values_secrets",
                return_value=(["role.yaml"], [], []),
            )
        )
        stack.enter_context(apply_module.click.Context(apply_module.apply))
        failed = _call_real_apply(apply_module, case)
    return {"events": events, "failed": failed}


def _call_real_apply(module: ModuleType, case: dict) -> bool:
    try:
        module.apply.callback(
            files=["templates"],
            values=[],
            secrets=[],
            dryrun=case["dryrun"],
            delete_existing=case["recreate"],
            workers=3,
            retry_count=4,
            retry_interval=0,
            silent=True,
        )
    except RuntimeError:
        return True
    return False


def _selection(*, branch: str | None = None) -> dict:
    module = importlib.import_module("riocli.chart.apply")
    selected = []

    class Recorder:
        def __init__(self, **fields: object) -> None:
            selected.append(fields["version"])

        def apply_chart(self, *_args: object, **_kwargs: object) -> None:
            pass

        def cleanup(self) -> None:
            pass

    messages = []
    with (
        patch.object(module, "Chart", Recorder),
        patch.object(
            module.click,
            "secho",
            side_effect=lambda message, **_kwargs: messages.append(message),
        ),
    ):
        module.apply_chart.callback(
            chart="sample", values=[], secrets=[], branch=branch, workers=3
        )
    return {"version": selected[0], "warned": bool(messages)}


def _capture(config: dict, cli_root: Path) -> dict:
    util, chart_module, apply_module = _modules(cli_root)
    requests = []

    def get(url: str) -> SimpleNamespace:
        requests.append(url)
        return SimpleNamespace(ok=True, text=yaml.safe_dump(config["index"]))

    with (
        _offline_requests(),
        patch.object(util.requests, "get", side_effect=get),
        redirect_stdout(io.StringIO()),
        redirect_stderr(io.StringIO()),
    ):
        output = _catalog(util, config)
        output["selection"] = _selection()
        output["index_selection"] = _source_decisions(util, requests)
        output["forwarding"] = {
            case["id"]: _forward(chart_module, case) for case in config["forwarding"]
        }
        output["recreation"] = {
            case["id"]: _recreation(apply_module, case) for case in config["recreation"]
        }
        output["first_package_url"] = _package_url(chart_module)
        output["failures"] = _failure_decisions(util, chart_module, config["failures"])
    return output


def _failed_call(callback: Callable) -> bool:
    try:
        callback()
    except Exception:  # noqa: BLE001 - reference CLI has generic acquisition errors
        return True
    return False


def _failure_decisions(util: ModuleType, module: ModuleType, cases: dict) -> dict:
    return {
        "branch": _failed_branch(util, cases["branch"]),
        "package": _failed_package(module, cases["package_urls"]),
    }


def _failed_branch(util: ModuleType, branch: str) -> dict:
    requested = []

    def get(url: str) -> SimpleNamespace:
        requested.append(url)
        return SimpleNamespace(ok=False)

    with patch.object(util.requests, "get", side_effect=get):
        failed = _failed_call(lambda: _selection(branch=branch))
    return {"failed": failed, "requests": requested}


def _failed_package(module: ModuleType, urls: list[str]) -> dict:
    requested = []

    def get(url: str) -> None:
        requested.append(url)
        msg = "controlled unusable first package location"
        raise module.requests.exceptions.MissingSchema(msg)

    chart = module.Chart(name="sample", version="2", urls=urls)
    try:
        with (
            patch.object(module.requests, "get", side_effect=get),
            patch.object(chart, "extract_chart") as extraction,
        ):
            failed = _failed_call(chart.download_chart)
    finally:
        chart.cleanup()
    return {"failed": failed, "requests": requested, "extracted": extraction.called}


def _package_url(module: ModuleType) -> str:
    requested = []

    def get(url: str) -> SimpleNamespace:
        requested.append(url)
        return SimpleNamespace(content=b"controlled-package")

    chart = module.Chart(
        name="sample",
        version="2",
        urls=["https://charts.example/first.tgz", "https://charts.example/second.tgz"],
    )
    try:
        with (
            patch.object(module.requests, "get", side_effect=get),
            patch.object(chart, "extract_chart"),
        ):
            chart.download_chart()
    finally:
        chart.cleanup()
    return requested[0]


def capture_workflows(output: Path, cli_root: Path, *, write: bool) -> None:
    """Capture CLI decisions or verify recorded source/environment parity."""
    from scripts.capture_apply_parity import (  # noqa: PLC0415 - explicit CLI oracle
        _check_provenance,
        _metadata,
        _output_json,
        _output_yaml,
        _sha,
    )

    descriptor = output / "cases.yaml"
    config = yaml.safe_load(descriptor.read_text())
    versions = _metadata(cli_root)
    sources = {"cases.yaml": _sha(descriptor.read_bytes())}
    for relative in [
        "riocli/chart/util.py",
        "riocli/chart/chart.py",
        "riocli/chart/apply.py",
        "riocli/apply/__init__.py",
    ]:
        sources[relative] = _sha((cli_root / relative).read_bytes())
    sources["oracle.py"] = _sha(Path(__file__).read_bytes())
    sources.update(_metadata_sources(output.parent / "metadata"))
    provenance = output / "provenance.json"
    if not write:
        _check_provenance(provenance, versions, sources)
    _output_yaml(output / "outputs.yaml", _capture(config, cli_root), write=write)
    if write:
        _output_json(
            provenance,
            {
                "versions": versions,
                "sources": sources,
                "command": (
                    "scripts/capture_apply_parity.py --suite chart-workflows --write"
                ),
            },
            write=True,
        )


def _source_decisions(util: ModuleType, requests: list[str]) -> dict[str, str]:
    decisions = {}
    for name, location in [
        ("default", None),
        ("custom", "https://custom.test/index.yaml"),
        ("empty_override", ""),
    ]:
        util.fetch_index(location)
        decisions[name] = requests[-1]
    _selection(branch="bug/fix some")
    decisions["branch"] = requests[-1]
    _selection(branch="")
    decisions["empty_branch"] = requests[-1]
    return decisions


def _metadata_sources(root: Path) -> dict[str, str]:
    from scripts.capture_apply_parity import _sha  # noqa: PLC0415 - tooling shared hashing

    provenance = root / "provenance.json"
    data = json.loads(provenance.read_text())
    hashes = {"metadata/provenance.json": _sha(provenance.read_bytes())}
    for relative, expected in data.get("sources", {}).items():
        local = Path(relative).relative_to("incubator")
        actual = _sha((root / local).read_bytes())
        if actual != expected:
            msg = f"metadata source hash drift: {local}"
            raise ValueError(msg)
        hashes[f"metadata/{local.as_posix()}"] = actual
    return hashes
