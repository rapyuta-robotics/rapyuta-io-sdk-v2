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

"""Documented examples preview both modes with explicit source/action boundaries."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml

from rapyuta_io_sdk_v2 import AsyncClient, Client
from rapyuta_io_sdk_v2.chart import AsyncChart, Chart, branch_repository_url
from tests.chart.helpers import PlatformRecorder, repository_response


@pytest.mark.parametrize("example", ["sync_chart.py", "async_chart.py"])
@pytest.mark.parametrize("action", ["inspect", "apply", "delete"])
def test_example_local_preview(example: str, action: str, chart_dir: Path) -> None:
    command = [
        sys.executable,
        str(Path("examples/chart") / example),
        "--directory",
        str(chart_dir),
        "--action",
        action,
        "--dry-run",
    ]
    result = subprocess.run(  # noqa: S603 - fixed interpreter and fixture example arguments
        command,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(Path.cwd())},
    )
    assert "viewer" in result.stdout


@pytest.mark.parametrize("example", ["sync_chart.py", "async_chart.py"])
def test_example_live_action_requires_explicit_config(
    example: str, chart_dir: Path
) -> None:
    command = [
        sys.executable,
        str(Path("examples/chart") / example),
        "--directory",
        str(chart_dir),
        "--action",
        "apply",
    ]
    result = subprocess.run(  # noqa: S603 - fixed interpreter and fixture example arguments
        command, capture_output=True, text=True, check=False
    )
    assert result.returncode != 0
    assert "--config" in result.stderr


@pytest.fixture(params=["sync_chart", "async_chart"], ids=["sync", "async"])
def chart_example(request: pytest.FixtureRequest) -> object:
    return importlib.import_module(f"examples.chart.{request.param}")


async def _run_example(module: object, arguments: list[str]) -> int:
    if inspect.iscoroutinefunction(module.main):
        return await module.main(arguments)
    return await asyncio.to_thread(module.main, arguments)


@pytest.fixture(params=["archive", "custom", "branch"])
def example_source(
    chart_dir: Path,
    archive_bytes: object,
    chart_example: object,
    *,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> object:
    return _controlled_example_source(
        chart_dir,
        archive_bytes,
        chart_example,
        kind=request.param,
        monkeypatch=monkeypatch,
    )


def _controlled_example_source(
    root: Path,
    pack: object,
    module: object,
    *,
    kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> object:
    state = SimpleNamespace(arguments=[], requests=[], clients=[], index=None)
    if kind == "archive":
        archive = root.parent / "example.tgz"
        archive.write_bytes(pack(root))
        state.arguments = ["--archive", str(archive)]
        return state
    state.arguments = [
        "--chart",
        "sample:1.0.0",
        "--repository",
        "https://custom.test/index.yaml",
    ]
    state.index = "https://custom.test/index.yaml"
    if kind == "branch":
        state.arguments += ["--branch", "bug/fix some"]
        state.index = branch_repository_url("bug/fix some")
    respond = repository_response(pack(root))

    def response(request: httpx.Request) -> httpx.Response:
        state.requests.append(str(request.url))
        return respond(request)

    native = inspect.iscoroutinefunction(module.main)
    original = httpx.AsyncClient if native else httpx.Client

    class OwnedClient(original):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(transport=httpx.MockTransport(response), **kwargs)
            state.clients.append(self)

    monkeypatch.setattr(httpx, original.__name__, OwnedClient)
    return state


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["inspect", "apply", "delete"])
async def test_examples_archive_and_controlled_remote_workflows(
    chart_example: object,
    example_source: object,
    *,
    action: str,
    capsys: pytest.CaptureFixture,
) -> None:
    arguments = [*example_source.arguments, "--action", action, "--dry-run"]
    if action == "apply":
        arguments.append("--delete-existing")
    assert await _run_example(chart_example, arguments) == 0
    output = capsys.readouterr().out
    assert "viewer" in output
    if action == "apply":
        assert output.index('"operation": "delete"') < output.index(
            '"operation": "apply"'
        )
    assert all(client.is_closed for client in example_source.clients)
    if example_source.index:
        assert example_source.requests[0] == example_source.index
        assert example_source.requests == [
            example_source.index,
            "https://chart.test/chart.tgz",
        ]


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--directory", "a", "--archive", "b"],
        ["--chart", "sample", "--action", "unknown"],
        ["--directory", "a", "--action", "delete"],
    ],
)
def test_example_source_action_and_config_constraints(
    chart_example: object, arguments: list[str]
) -> None:
    with pytest.raises(SystemExit):
        vars(chart_example)["_arguments"](arguments)


@pytest.mark.asyncio
@pytest.mark.parametrize("decrypt", [False, True])
async def test_plain_and_explicit_encrypted_inputs_have_matching_semantics(
    chart_dir: Path,
    chart_example: object,
    *,
    decrypt: bool,
    example_decryption: object,
    capsys: pytest.CaptureFixture,
) -> None:
    calls = example_decryption(chart_example)
    arguments = _render_input_arguments(chart_dir)
    if decrypt:
        arguments += [
            "--encrypted-secrets",
            "first.enc",
            "--encrypted-secrets",
            "second.enc",
        ]
    assert await _run_example(chart_example, arguments) == 0
    expected = "second-decrypted-2-context" if decrypt else "second-plain-2-context"
    assert expected in capsys.readouterr().out
    assert calls == ([Path("first.enc"), Path("second.enc")] if decrypt else [])


@pytest.fixture
def example_decryption(monkeypatch: pytest.MonkeyPatch) -> object:
    def install(module: object) -> list:
        calls = []

        def decode(path: Path) -> dict:
            calls.append(path)
            return {"token": f"decrypted-{len(calls)}"}

        async def native(path: Path) -> dict:
            return decode(path)

        name = (
            "async_decrypt_secret_file"
            if inspect.iscoroutinefunction(module.main)
            else "decrypt_secret_file"
        )
        monkeypatch.setattr(
            module, name, native if name.startswith("async") else decode
        )
        return calls

    return install


def _render_input_arguments(root: Path) -> list[str]:
    (root / "templates/role.yaml").write_text(
        "kind: Role\nmetadata:\n"
        "  name: '{{ name }}-{{ secrets.token }}-{{ rio.org }}'\n"
        "spec: {rules: []}\n"
    )
    arguments = ["--directory", str(root), "--action", "inspect"]
    for namespace in ["values", "secrets"]:
        for index, value in enumerate(["first", "second"], 1):
            path = root.parent / f"{namespace}-{index}.yaml"
            path.write_text(
                yaml.safe_dump(
                    {"name": value}
                    if namespace == "values"
                    else {"token": f"plain-{index}"}
                )
            )
            arguments += [f"--{namespace}", str(path)]
    rio = root.parent / "rio.yaml"
    rio.write_text("org: context\n")
    return [*arguments, "--rio", str(rio)]


@pytest.mark.asyncio
async def test_example_chart_failure_returns_failure_with_source(
    chart_dir: Path,
    chart_example: object,
    capsys: pytest.CaptureFixture,
) -> None:
    (chart_dir / "Chart.yaml").unlink()
    assert await _run_example(chart_example, ["--directory", str(chart_dir)]) == 1
    output = capsys.readouterr().out
    assert "metadata" in output
    assert str(chart_dir) in output


@pytest.mark.parametrize("filename", ["sync_chart.py", "async_chart.py"])
def test_example_import_has_no_authentication_platform_or_cli_side_effects(
    filename: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        msg = "I/O during example import"
        raise AssertionError(msg)

    monkeypatch.setattr(Client, "__init__", forbidden)
    monkeypatch.setattr(AsyncClient, "__init__", forbidden)
    monkeypatch.setattr(Chart, "load", forbidden)
    monkeypatch.setattr(AsyncChart, "load", forbidden)
    before = set(sys.modules)
    namespace = runpy.run_path(
        str(Path("examples/chart") / filename), run_name="import_smoke"
    )
    assert callable(namespace["main"])
    assert not any(name.startswith("riocli") for name in set(sys.modules) - before)


@pytest.fixture
def configured_example_client(
    monkeypatch: pytest.MonkeyPatch, chart_example: object
) -> list:
    clients = []
    original = (
        AsyncClient if inspect.iscoroutinefunction(chart_example.main) else Client
    )

    def controlled(configuration: object) -> object:
        client = original(configuration)
        recorder = PlatformRecorder(None)
        recorder.fail = "create"

        def create(resource: object, **kwargs: object) -> object:
            return recorder.create_role(resource, **kwargs)

        async def native_create(resource: object, **kwargs: object) -> object:
            return create(resource, **kwargs)

        async def native_delete(*args: object, **kwargs: object) -> None:
            recorder.delete_role(*args, **kwargs)

        client.create_role = native_create if original is AsyncClient else create
        client.delete_role = (
            native_delete if original is AsyncClient else recorder.delete_role
        )
        clients.append(client)
        return client

    monkeypatch.setattr(chart_example, original.__name__, controlled)
    return clients


@pytest.mark.asyncio
async def test_configured_example_failure_prints_both_phases_and_closes_owned_client(
    chart_dir: Path,
    chart_example: object,
    *,
    configured_example_client: list,
    capsys: pytest.CaptureFixture,
) -> None:
    config = chart_dir.parent / "explicit-config.json"
    config.write_text(
        json.dumps(
            {"auth_token": "chart-test", "organization_id": "org", "environment": "ga"}
        )
    )
    result = await _run_example(
        chart_example,
        [
            "--directory",
            str(chart_dir),
            "--config",
            str(config),
            "--action",
            "apply",
            "--delete-existing",
        ],
    )
    assert result == 1
    output = capsys.readouterr().out
    assert output.index('"operation": "delete"') < output.index('"operation": "apply"')
    assert '"write_uncertain": true' in output
    assert configured_example_client
    assert all(client.c.is_closed for client in configured_example_client)
    assert configured_example_client[0].config.organization_guid == "org"


def test_example_parsers_have_identical_full_argument_contract() -> None:
    arguments = [
        "--chart",
        "sample:1",
        "--repository",
        "https://custom.test/index.yaml",
        "--branch",
        "feature/x",
        "--values",
        "one.yaml",
        "--values",
        "two.yaml",
        "--secrets",
        "plain.yaml",
        "--encrypted-secrets",
        "encrypted.yaml",
        "--rio",
        "rio.yaml",
        "--config",
        "config.json",
        "--action",
        "apply",
        "--dry-run",
        "--delete-existing",
    ]
    modules = [
        importlib.import_module(f"examples.chart.{name}")
        for name in ["sync_chart", "async_chart"]
    ]
    parsed = [vars(vars(module)["_arguments"](arguments)) for module in modules]
    assert parsed[0] == parsed[1]
    assert parsed[0]["values"] == [Path("one.yaml"), Path("two.yaml")]
    assert parsed[0]["encrypted_secrets"] == [Path("encrypted.yaml")]
