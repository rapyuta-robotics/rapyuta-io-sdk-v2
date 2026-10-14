# Copyright 2026 Rapyuta Robotics
"""Execute the advertised examples against isolated platform contracts."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
import pytest_asyncio

from examples.devices import command, command_async, manage, manage_async
from rapyuta_io_sdk_v2 import AsyncClient, Client, Configuration
from rapyuta_io_sdk_v2.exceptions import DeviceCommandCancelled, DeviceCommandTimeout
from tests.data.device_data import BASE, CASES, PENDING, success

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@dataclass
class ExampleService:
    """Isolated controller responses with observable command progress."""

    scenario: str = "complete"
    submissions: list[object] = field(default_factory=list)
    polls: int = 0
    requests: list[httpx.Request] = field(default_factory=list)

    def respond(self, request: httpx.Request) -> httpx.Response:
        """Replay a command batch or a source-backed management envelope."""
        self.requests.append(request)
        if request.url.path == BASE + "/cmd/":
            payload = json.loads(request.content)
            self.submissions.append(payload)
            data = {
                target: "" if index == 0 else "ready"
                for index, target in enumerate(payload["device_ids"])
            }
            if payload["run_async"] and not payload["bg"]:
                data = {"jid": "job", "minions": payload["device_ids"]}
            return httpx.Response(200, content=success(data))
        if request.url.path == BASE + "/cmd/job":
            self.polls += 1
            if self.scenario == "pending" and self.polls > 1:
                return httpx.Response(400, json=PENDING)
            target = request.url.params.get_list("device_id")[0]
            return httpx.Response(
                200, content=success({target: "" if self.polls == 1 else "ready"})
            )
        case = next(
            case
            for case in CASES
            if request.method == case.verb and request.url.path == BASE + case.path
        )
        return httpx.Response(200, content=case.response)

    async def respond_async(self, request: httpx.Request) -> httpx.Response:
        """Suspend retrieval for the external cancellation demonstration."""
        if self.scenario == "cancel" and request.url.path == BASE + "/cmd/job":
            await asyncio.sleep(1)
        return self.respond(request)


@pytest_asyncio.fixture
async def examples_target() -> AsyncIterator[
    tuple[ExampleService, Client, AsyncClient]
]:
    service = ExampleService()
    config = Configuration(
        auth_token="fake", project_guid="source", core_api_host="https://core"
    )
    sync = Client(config)
    async_ = AsyncClient(config)
    sync.c.close()
    await async_.c.aclose()
    sync.c = httpx.Client(transport=httpx.MockTransport(service.respond))
    async_.c = httpx.AsyncClient(transport=httpx.MockTransport(service.respond_async))
    yield service, sync, async_
    sync.c.close()
    await async_.c.aclose()
    async_.sync_client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    "flags",
    [
        ["create", "--name", "robot-alpha"],
        ["onboarding", "--device", "device-a"],
        ["get", "--device", "device-a"],
        ["list"],
        ["select", "--selection", '{"operator":"$and"}'],
        ["update", "--device", "device-a", "--description", "Warehouse robot"],
        ["delete", "--device", "device-a"],
        ["label-list", "--device", "device-a"],
        ["label-create", "--device", "device-a", "--key", "fleet", "--value", "alpha"],
        ["label-update", "--record-id", "1", "--value", "beta"],
        ["label-delete", "--record-id", "1"],
        ["config-list", "--device", "device-a"],
        [
            "config-create",
            "--device",
            "device-a",
            "--key",
            "setting",
            "--value",
            "value",
        ],
        ["config-update", "--record-id", "2", "--value", "new"],
        ["config-delete", "--record-id", "2"],
        ["vpn-enable", "--device", "device-a"],
        ["vpn-disable", "--device", "device-a"],
        ["vpn-enable", "--device", "device-a", "--advertise-routes"],
        [
            "parameters",
            "--target",
            "device-a",
            "--target",
            "missing",
            "--tree",
            "alpha",
        ],
        ["migrate", "--device", "device-a", "--destination-project", "destination"],
    ],
)
async def test_management_examples(
    *,
    mode: str,
    flags: list[str],
    examples_target: tuple[ExampleService, Client, AsyncClient],
    capsys: pytest.CaptureFixture[str],
) -> None:
    service, sync, async_ = examples_target
    args = manage.parser().parse_args(flags)
    result = (
        manage.invoke(sync, args)
        if mode == "sync"
        else await manage_async.invoke(async_, args)
    )
    if args.action in {"vpn-enable", "vpn-disable"}:
        _verify_example_vpn(service.requests, args)
    manage.report(result, args)
    assert "fixture-onboarding-token" not in capsys.readouterr().out
    assert sync.config.project_guid == async_.config.project_guid == "source"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("deferred", [False, True])
@pytest.mark.parametrize("targets", [("a",), ("a", "b", "c")])
async def test_helper_examples(
    *,
    mode: str,
    deferred: bool,
    targets: tuple[str, ...],
    examples_target: tuple[ExampleService, Client, AsyncClient],
) -> None:
    service, sync, async_ = examples_target
    flags = [
        "--command",
        "printf ''",
        "--mode",
        "deferred" if deferred else "immediate",
        "--poll-interval",
        "0.001",
    ]
    for target in targets:
        flags.extend(["--device", target])
    args = command.parser().parse_args(flags)
    result = (
        command.invoke(sync, args)
        if mode == "sync"
        else await command_async.invoke(async_, args)
    )
    assert result.responses[0].output == ""
    assert result.missing_devices == ()
    assert tuple(item.device_guid for item in result.responses) == targets
    assert len(service.submissions) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_example_partial_timeout(
    *, mode: str, examples_target: tuple[ExampleService, Client, AsyncClient]
) -> None:
    service, sync, async_ = examples_target
    service.scenario = "pending"
    args = command.parser().parse_args(
        [
            "--device",
            "a",
            "--device",
            "b",
            "--command",
            "true",
            "--wait-timeout",
            "0.01",
            "--poll-interval",
            "0.001",
        ]
    )
    with pytest.raises(DeviceCommandTimeout) as caught:
        await _invoke_command(mode, sync, async_, args=args)
    assert caught.value.failure.stage == "timeout"
    assert caught.value.partial_result.responses[0].output == ""
    assert caught.value.failure.missing_devices == ("b",)


async def _invoke_command(
    mode: str, sync: Client, async_: AsyncClient, *, args: object
) -> object:
    return (
        command.invoke(sync, args)
        if mode == "sync"
        else await command_async.invoke(async_, args)
    )


@pytest.mark.asyncio
async def test_async_example_rethrows_cancellation(
    *,
    examples_target: tuple[ExampleService, Client, AsyncClient],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    service, _, async_ = examples_target
    service.scenario = "cancel"
    monkeypatch.setattr(command_async, "AsyncClient", lambda _config: async_)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "command_async",
            "--device",
            "a",
            "--command",
            "true",
            "--cancel-after",
            "0.01",
        ],
    )
    with pytest.raises(DeviceCommandCancelled):
        await command_async.main()
    assert "cancellation" in capsys.readouterr().out
    assert async_.c.is_closed
    assert len(service.submissions) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    "extra",
    [
        ["--direct", "--mode", "immediate"],
        ["--direct", "--background"],
        ["--direct"],
        ["--jid", "job"],
    ],
)
async def test_direct_command_examples(
    *,
    mode: str,
    extra: list[str],
    examples_target: tuple[ExampleService, Client, AsyncClient],
) -> None:
    _, sync, async_ = examples_target
    args = command.parser().parse_args(["--device", "a", "--command", "true", *extra])
    result = await _invoke_command(mode, sync, async_, args=args)
    assert result.status == "success"


def test_documented_quickstart_snippets(
    examples_target: tuple[ExampleService, Client, AsyncClient],
    capsys: pytest.CaptureFixture[str],
) -> None:

    _, client, _ = examples_target
    document = Path("specs/002-device-management/quickstart.md").read_text()
    namespace = {"client": client}
    for snippet in re.findall(r"```python\n(.*?)```", document, re.DOTALL):
        # Execute trusted repository examples against isolated fixtures.
        exec(compile(snippet, "quickstart.md", "exec"), namespace)  # noqa: S102
    assert "fixture-onboarding-token" not in capsys.readouterr().out


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_actual_transport_budget_and_ownership(
    *, mode: str, examples_target: tuple[ExampleService, Client, AsyncClient]
) -> None:
    service, sync, async_ = examples_target
    target = sync if mode == "sync" else async_
    timeout = target.c.timeout
    transport = target.c
    context = target.config
    wait_budget = 0.1
    args = command.parser().parse_args(
        [
            "--device",
            "a",
            "--device",
            "b",
            "--command",
            "true",
            "--wait-timeout",
            str(wait_budget),
            "--poll-interval",
            "0.001",
        ]
    )
    result = await _invoke_command(mode, sync, async_, args=args)
    assert result.missing_devices == ()
    assert target.c is transport
    assert target.config is context
    assert target.c.timeout == timeout
    assert not target.c.is_closed
    assert service.requests[1].url.params.multi_items() == [
        ("device_id", "a"),
        ("device_id", "b"),
    ]
    assert service.requests[2].url.params.multi_items() == [("device_id", "b")]
    for request in service.requests:
        assert all(
            0 < cap <= wait_budget for cap in request.extensions["timeout"].values()
        )


def _verify_example_vpn(requests: list[httpx.Request], args: object) -> None:
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "PATCH"
    assert request.url.path == BASE + "/devices/device-a/daemons"
    assert request.headers["project"] == "source"
    assert json.loads(request.content) == {
        "vpn": args.action == "vpn-enable",
        "config": {"vpn": {"advertise_routes": args.advertise_routes}},
    }
