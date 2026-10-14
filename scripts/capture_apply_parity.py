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

"""Capture and replay the rio CLI's local Apply parser as a fixture oracle."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from copy import deepcopy
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

import yaml
from benedict import benedict

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

# Direct execution puts scripts/, rather than the checkout root, on sys.path.
# Keep package imports available to the workflow oracle in either execution mode.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.chart_workflow_oracle import capture_workflows

DEFAULT_OUTPUT = Path("tests/apply/fixtures/parity")
CHARTS = ("postgis", "gateway", "gostproxy")


class CLIParser(Protocol):
    """Small surface used from the CLI's local Apply parser."""

    values: benedict

    def _load_manifests(self, path: str) -> list[dict[str, Any]] | None:
        """Render and parse one local manifest."""
        ...


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git(root: Path, *args: str) -> str:
    executable = shutil.which("git")
    if executable is None:
        msg = "git is required for fixture provenance"
        raise RuntimeError(msg)
    return subprocess.check_output(  # noqa: S603 - fixed git executable and args
        [executable, "-C", str(root), *args], text=True
    ).strip()


def _metadata(cli_root: Path, charts_root: Path | None = None) -> dict[str, str]:
    _add_cli_paths(cli_root)
    result = {
        "python": ".".join(map(str, sys.version_info[:3])),
        "ansible": version("ansible-core"),
        "jinja": version("jinja2"),
        "cli_version": _checkout_cli_version(cli_root),
        "cli_revision": _git(cli_root, "rev-parse", "HEAD"),
    }
    if charts_root is not None:
        result["chart_revision"] = _git(charts_root, "rev-parse", "HEAD")
    return result


def _add_cli_paths(cli_root: Path) -> None:
    parser_path = cli_root / "riocli" / "apply" / "parse.py"
    if not parser_path.is_file():
        msg = f"rio CLI parser unavailable in --cli-root: {cli_root}"
        raise ValueError(msg)
    _check_cli_modules(cli_root)
    root_path = str(cli_root)
    if root_path in sys.path:
        sys.path.remove(root_path)
    sys.path.insert(0, root_path)
    cli_site = (
        cli_root
        / ".venv"
        / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    )
    if cli_site.is_dir():
        site_path = str(cli_site)
        if site_path not in sys.path:
            sys.path.append(site_path)


def _check_cli_modules(cli_root: Path) -> None:
    for name, module in tuple(sys.modules.items()):
        if name != "riocli" and not name.startswith("riocli."):
            continue
        locations = [getattr(module, "__file__", None)]
        locations.extend(getattr(module, "__path__", ()))
        for location in filter(None, locations):
            if not Path(location).resolve().is_relative_to(cli_root.resolve()):
                msg = (
                    f"rio CLI module {name} from {location} "
                    f"outside --cli-root {cli_root}"
                )
                raise RuntimeError(msg)


def _checkout_cli_version(cli_root: Path) -> str:
    bootstrap = cli_root / "riocli" / "bootstrap.py"
    tree = ast.parse(bootstrap.read_text(encoding="utf-8"), filename=str(bootstrap))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in statement.targets
        ):
            value = ast.literal_eval(statement.value)
            if isinstance(value, str):
                return value
    msg = f"rio CLI version unavailable in --cli-root: {cli_root}"
    raise ValueError(msg)


def _cli_parser(cli_root: Path) -> CLIParser:
    _add_cli_paths(cli_root)
    from riocli.apply.parse import Applier  # noqa: PLC0415 - explicit CLI checkout
    from riocli.apply.util import init_jinja_environment  # noqa: PLC0415

    _check_cli_modules(cli_root)

    parser = Applier.__new__(Applier)
    parser.environment = init_jinja_environment()
    return cast("CLIParser", parser)


def _merge(base: dict[str, Any], changes: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = deepcopy(value)
    return base


def _set_environment(values: Mapping[str, str | None]) -> None:
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@contextmanager
def _case_inputs(case: Mapping[str, Any]) -> Iterator[None]:
    from riocli.apply import filters  # noqa: PLC0415 - patch CLI provider only

    before = {key: os.environ.get(key) for key in case.get("env", {})}
    provider = filters.get_device_ip_interfaces
    device = case.get("device")
    try:
        _set_environment(case.get("env", {}))

        def controlled_device(_name: str) -> dict[str, list[str]]:
            if device is None:
                case_id = case.get("id", "<unknown>")
                msg = f"no controlled device response for capture case {case_id}"
                raise RuntimeError(msg)
            return cast("dict[str, list[str]]", device)

        filters.get_device_ip_interfaces = controlled_device
        yield
    finally:
        filters.get_device_ip_interfaces = provider
        _set_environment(before)


def _parse_case(
    parser: CLIParser,
    case: Mapping[str, Any],
    manifests: list[Path],
    *,
    values: dict[str, Any],
) -> list[dict[str, Any]]:
    parser.values = benedict(
        _merge(values, {"rio": case.get("rio", {}), "secrets": {}})
    )
    with _case_inputs(case):
        return [
            document
            for manifest in manifests
            for document in (parser._load_manifests(str(manifest)) or [])  # noqa: SLF001 - CLI parser contract
            if document is not None
        ]


def _case_manifest(case: Mapping[str, Any], directory: Path, *, write: bool) -> Path:
    path = directory / f"{case['id']}.yaml"
    if write:
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text(case["manifest"], encoding="utf-8")
    elif path.read_text(encoding="utf-8") != case["manifest"]:
        msg = f"direct filter manifest source drift: {path}"
        raise ValueError(msg)
    return path


def _capture_direct_case(
    parser: CLIParser, case: Mapping[str, Any], directory: Path, *, write: bool
) -> tuple[list[dict[str, Any]] | None, dict[str, str] | None]:
    manifest = _case_manifest(case, directory, write=write)
    try:
        documents = _parse_case(parser, case, [manifest], values={})
    except Exception as exc:
        if not case.get("expected_error"):
            raise
        return None, {
            "id": case["id"],
            "type": type(exc).__name__,
            "message": str(exc).replace(
                str(manifest.resolve()), f"manifests/{manifest.name}"
            ),
        }
    if case.get("expected_error"):
        msg = f"expected CLI failure did not occur: {case['id']}"
        raise AssertionError(msg)
    return documents, None


def _direct_cases(
    parser: CLIParser, cases: list[dict[str, Any]], directory: Path, *, write: bool
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, str]]]:
    outputs: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []
    for case in cases:
        documents, error = _capture_direct_case(
            parser, case, directory / "manifests", write=write
        )
        if documents is not None:
            outputs[case["id"]] = documents
        if error is not None:
            errors.append(error)
    return outputs, errors


def _direct_suite(suite: str, output: Path, cli_root: Path, *, write: bool) -> None:
    directory = output / suite
    cases_file = directory / "cases.yaml"
    cases = yaml.safe_load(cases_file.read_text(encoding="utf-8"))["cases"]
    provenance_file = directory / "provenance.json"
    metadata = _metadata(cli_root)
    sources = {
        "cases.yaml": _sha(cases_file.read_bytes()),
        **{case["id"]: _sha(case["manifest"].encode()) for case in cases},
    }
    if not write:
        _check_provenance(provenance_file, metadata, sources)
    parser = _cli_parser(cli_root)
    outputs, errors = _direct_cases(parser, cases, directory, write=write)
    _output_yaml(directory / "outputs.yaml", outputs, write=write)
    if suite == "rio-filters":
        _output_json(directory / "errors.json", errors, write=write)
    if write:
        _output_json(
            provenance_file,
            {
                "versions": metadata,
                "sources": sources,
                "cases": cases,
                "command": f"scripts/capture_apply_parity.py --suite {suite} --write",
            },
            write=True,
        )


def _tracked_chart_sources(charts_root: Path, chart: str) -> list[Path]:
    relative = f"incubator/{chart}/templates"
    names = _git(charts_root, "ls-files", "--", relative).splitlines()
    paths = [charts_root / name for name in names if name.endswith(".yaml")]
    if not paths or not all(path.is_file() for path in paths):
        msg = f"tracked chart templates unavailable: {chart}"
        raise ValueError(msg)
    return paths


def _copy_chart_source(
    source: Path,
    charts_root: Path,
    directory: Path,
    *,
    sources: dict[str, str],
    write: bool,
) -> Path:
    target = directory / source.relative_to(charts_root / "incubator" / directory.name)
    source_key = str(source.relative_to(charts_root))
    sources[source_key] = _sha(source.read_bytes())
    if write:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    if not target.is_file() or _sha(target.read_bytes()) != sources[source_key]:
        msg = f"copied chart source differs: {target}"
        raise ValueError(msg)
    return target


def _reconcile_chart_templates(
    directory: Path, copied: list[Path], *, write: bool
) -> None:
    extras = sorted(set((directory / "templates").rglob("*.yaml")) - set(copied))
    if not extras:
        return
    if not write:
        names = ", ".join(str(path.relative_to(directory)) for path in extras)
        msg = f"unexpected copied chart templates: {names}"
        raise ValueError(msg)
    for path in extras:
        path.unlink()


def _chart_inputs(
    output: Path,
    charts_root: Path,
    chart: str,
    *,
    sources: dict[str, str],
    write: bool,
) -> tuple[list[Path], dict[str, Any], list[dict[str, Any]]]:
    directory = output / chart
    descriptor = directory / "cases.yaml"
    config = yaml.safe_load(descriptor.read_text(encoding="utf-8"))
    source_paths = _tracked_chart_sources(charts_root, chart)
    base_relative = f"incubator/{chart}/{config['base_values']}"
    if (
        _git(charts_root, "ls-files", "--error-unmatch", "--", base_relative)
        != base_relative
    ):
        msg = f"untracked base values: {base_relative}"
        raise ValueError(msg)
    source_paths.append(charts_root / base_relative)
    sources[f"{chart}/cases.yaml"] = _sha(descriptor.read_bytes())
    copied: list[Path] = []
    for source in source_paths:
        target = _copy_chart_source(
            source, charts_root, directory, sources=sources, write=write
        )
        if "templates" in source.parts:
            copied.append(target)
    _reconcile_chart_templates(directory, copied, write=write)
    base = yaml.safe_load((directory / config["base_values"]).read_text())
    return copied, base, config["cases"]


def _render_chart_cases(
    parser: CLIParser,
    manifests: list[Path],
    base: dict[str, Any],
    *,
    cases: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    return {
        case["id"]: _parse_case(
            parser, case, manifests, values=_merge(deepcopy(base), case["overrides"])
        )
        for case in cases
    }


def _chart_case_metadata(
    chart_inputs: dict[str, tuple[list[Path], dict[str, Any], list[dict[str, Any]]]],
    output: Path,
) -> list[dict[str, Any]]:
    result = []
    for chart, (manifests, base, cases) in chart_inputs.items():
        descriptor = yaml.safe_load((output / chart / "cases.yaml").read_text())
        for case in cases:
            effective = _merge(deepcopy(base), case["overrides"])
            result.append(
                {
                    "id": f"{chart}/{case['id']}",
                    "values_sources": [f"{chart}/{descriptor['base_values']}"],
                    "case_descriptor": f"{chart}/cases.yaml",
                    "values_sha256": _sha(yaml.safe_dump(effective).encode()),
                    "templates": [str(path.relative_to(output)) for path in manifests],
                    "rio": case.get("rio", {}),
                    "project_guid": case.get("project_guid"),
                    "device": case.get("device"),
                }
            )
    return result


def _chart_suite(
    output: Path, cli_root: Path, charts_root: Path, *, write: bool
) -> None:
    provenance_file = output / "provenance.json"
    metadata = _metadata(cli_root, charts_root)
    sources: dict[str, str] = {}
    chart_inputs: dict[
        str, tuple[list[Path], dict[str, Any], list[dict[str, Any]]]
    ] = {}
    for chart in CHARTS:
        chart_inputs[chart] = _chart_inputs(
            output, charts_root, chart, sources=sources, write=write
        )
    case_metadata = _chart_case_metadata(chart_inputs, output)
    if not write:
        _check_provenance(provenance_file, metadata, sources, cases=case_metadata)
    parser = _cli_parser(cli_root)
    for chart, (manifests, base, cases) in chart_inputs.items():
        outputs = _render_chart_cases(parser, manifests, base, cases=cases)
        _output_yaml(output / chart / "outputs.yaml", outputs, write=write)
    if write:
        _output_json(
            provenance_file,
            {
                "versions": metadata,
                "sources": sources,
                "cases": case_metadata,
                "command": "scripts/capture_apply_parity.py --suite charts --write",
            },
            write=True,
        )


def _check_provenance(
    path: Path,
    versions: dict[str, str],
    sources: dict[str, str],
    *,
    cases: list[dict[str, Any]] | None = None,
) -> None:
    recorded = json.loads(path.read_text(encoding="utf-8"))
    for key, value in versions.items():
        if recorded["versions"].get(key) != value:
            msg = (
                f"{key} drift: recorded {recorded['versions'].get(key)}, actual {value}"
            )
            raise ValueError(msg)
    if recorded["sources"] != sources:
        msg = f"source or input hash drift: {path}"
        raise ValueError(msg)
    if cases is not None and recorded.get("cases") != cases:
        msg = f"recorded case input drift: {path}"
        raise ValueError(msg)


def _output_yaml(path: Path, value: object, *, write: bool) -> None:
    if write:
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    elif not _typed_equal(yaml.safe_load(path.read_text(encoding="utf-8")), value):
        msg = f"CLI output drift: {path}"
        raise ValueError(msg)


def _typed_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        return len(left) == len(right) and all(
            any(
                _typed_equal(left_key, right_key)
                and _typed_equal(left_value, right_value)
                for right_key, right_value in right.items()
            )
            for left_key, left_value in left.items()
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _typed_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def _output_json(path: Path, value: object, *, write: bool) -> None:
    if write:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    elif json.loads(path.read_text(encoding="utf-8")) != value:
        msg = f"CLI output drift: {path}"
        raise ValueError(msg)


def main(argv: list[str] | None = None) -> None:
    """Run selected CLI fixture captures or read-only replay checks."""
    argument = argparse.ArgumentParser(description=__doc__)
    argument.add_argument(
        "--suite",
        choices=("rio-filters", "ansible-filters", "charts", "chart-workflows"),
    )
    argument.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    argument.add_argument("--cli-root", type=Path, default=Path("../rapyuta-io-cli"))
    argument.add_argument("--charts-root", type=Path, default=Path("../rapyuta-charts"))
    mode = argument.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    options = argument.parse_args(argv)
    output = options.output.resolve()
    cli_root = options.cli_root.resolve()
    charts_root = options.charts_root.resolve()
    for suite in (
        (options.suite,)
        if options.suite
        else ("rio-filters", "ansible-filters", "charts")
    ):
        if suite == "chart-workflows":
            capture_workflows(output, cli_root, write=options.write)
        elif suite == "charts":
            _chart_suite(output, cli_root, charts_root, write=options.write)
        else:
            _direct_suite(suite, output, cli_root, write=options.write)
        sys.stdout.write(f"{suite}: {'captured' if options.write else 'verified'}\n")


if __name__ == "__main__":
    main()
