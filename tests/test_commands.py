"""Tests for standalone Device Management command polling helpers."""

from __future__ import annotations

import asyncio

import httpx
import pytest

import rapyuta_io_sdk_v2.commands as commands
from rapyuta_io_sdk_v2.context import RequestContext
from rapyuta_io_sdk_v2.models.device import DeviceCommandResponse


@pytest.mark.parametrize(
    "status_code,status",
    [
        (202, None),
        (204, None),
        (200, "pending"),
        (200, "queued"),
        (200, "running"),
        (200, "accepted"),
        (200, "RUNNING"),
    ],
)
def test_command_response_pending_statuses(status_code, status):
    result = DeviceCommandResponse(
        http_status_code=status_code, status=status, data={"status": "pending"}
    )
    assert result.is_pending
    assert "http_status_code" not in result.model_dump()


def test_nested_result_status_does_not_make_command_pending():
    result = DeviceCommandResponse(data={"status": "pending"})
    assert not result.is_pending


@pytest.mark.parametrize(
    "outer_status,data,expected_status,expected_data",
    [
        ("pending", None, None, None),
        ("pending", {"status": "completed", "data": 1}, "completed", 1),
    ],
)
def test_v1_envelope_pending_status_is_metadata(
    outer_status, data, expected_status, expected_data
):
    from rapyuta_io_sdk_v2._device_helpers import _command_response

    response = httpx.Response(
        200,
        json={"status": outer_status, "response": {"data": data}},
    )
    result = _command_response(data, response=response)

    assert result.status == expected_status
    assert result.data == expected_data
    assert result.envelope_status == outer_status
    assert result.http_status_code == 200
    assert result.is_pending
    assert "envelope_status" not in result.model_dump()
    assert "http_status_code" not in result.model_dump()


@pytest.mark.parametrize(
    "payload,expected",
    [
        (None, {}),
        ({}, {"data": {}}),
        ("done", {"data": "done"}),
        (42, {"data": 42}),
        (["done"], {"data": ["done"]}),
        ({"jid": "j1", "data": {"result": 1}}, {"jid": "j1", "data": {"result": 1}}),
        ({"result": 1}, {"data": {"result": 1}}),
    ],
)
def test_command_response_parsing(payload, expected):
    from rapyuta_io_sdk_v2._device_helpers import _command_response

    result = _command_response(payload)
    assert result.model_dump(exclude_none=True) == expected
    assert not result.is_pending


class _SyncCommandClient:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def get_command_result(self, jid, device_ids, *, context=None):
        self.calls.append((jid, device_ids, context))
        value = next(self.results)
        if isinstance(value, Exception):
            raise value
        return value


class _AsyncCommandClient:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    async def get_command_result(self, jid, device_ids, *, context=None):
        self.calls.append((jid, device_ids, context))
        value = next(self.results)
        if isinstance(value, Exception):
            raise value
        return value


def test_wait_for_command_result_retries_and_preserves_context(monkeypatch):
    now = [10.0]
    sleeps = []
    monkeypatch.setattr(commands.time, "monotonic", lambda: now[0])

    def sleep(delay):
        sleeps.append(delay)
        now[0] += delay

    monkeypatch.setattr(commands.time, "sleep", sleep)
    context = RequestContext(request_id="trace")
    client = _SyncCommandClient(
        [
            DeviceCommandResponse(http_status_code=202),
            DeviceCommandResponse(status="running"),
            DeviceCommandResponse(data={"result": "done"}),
        ]
    )

    result = commands.wait_for_command_result(
        client,
        "job-1",
        ["d1", "d1"],
        retry_interval=2,
        timeout=5,
        context=context,
    )

    assert result.data == {"result": "done"}
    assert len(client.calls) == 3
    assert all(call == ("job-1", ["d1", "d1"], context) for call in client.calls)
    assert sleeps == [2, 2]


def test_wait_helper_retries_parsed_v1_pending_envelope(monkeypatch):
    from rapyuta_io_sdk_v2._device_helpers import _command_response

    now = [0.0]
    monkeypatch.setattr(commands.time, "monotonic", lambda: now[0])

    def sleep(delay):
        now[0] += delay

    monkeypatch.setattr(commands.time, "sleep", sleep)
    pending = _command_response(
        None,
        response=httpx.Response(
            200, json={"status": "pending", "response": {"data": None}}
        ),
    )
    completed = _command_response(
        {"status": "completed", "data": {"ok": True}},
        response=httpx.Response(
            200,
            json={
                "status": "success",
                "response": {"data": {"status": "completed", "data": {"ok": True}}},
            },
        ),
    )
    client = _SyncCommandClient([pending, completed])

    result = commands.wait_for_command_result(
        client, "job", ["d1"], retry_interval=1, timeout=2
    )

    assert result.status == "completed"
    assert result.data == {"ok": True}
    assert result.envelope_status == "success"
    assert len(client.calls) == 2


def test_wait_for_command_result_times_out_without_request_after_deadline(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(commands.time, "monotonic", lambda: now[0])

    def sleep(delay):
        now[0] += delay

    monkeypatch.setattr(commands.time, "sleep", sleep)
    client = _SyncCommandClient([DeviceCommandResponse(http_status_code=202)] * 3)

    with pytest.raises(TimeoutError):
        commands.wait_for_command_result(
            client, "job", ["d1"], retry_interval=1, timeout=2
        )
    assert len(client.calls) == 2


def test_wait_for_command_result_propagates_client_errors(monkeypatch):
    monkeypatch.setattr(commands.time, "monotonic", lambda: 0.0)
    error = RuntimeError("request failed")
    client = _SyncCommandClient([error])

    with pytest.raises(RuntimeError, match="request failed"):
        commands.wait_for_command_result(client, "job", ["d1"])


@pytest.mark.parametrize(
    "retry_interval,timeout",
    [(0, 1), (1, 0), (float("inf"), 1), (1, float("nan"))],
)
def test_wait_helpers_reject_invalid_timing(retry_interval, timeout):
    sync_client = _SyncCommandClient([])
    async_client = _AsyncCommandClient([])
    with pytest.raises(ValueError):
        commands.wait_for_command_result(
            sync_client,
            "job",
            ["d1"],
            retry_interval=retry_interval,
            timeout=timeout,
        )

    async def run():
        with pytest.raises(ValueError):
            await commands.async_wait_for_command_result(
                async_client,
                "job",
                ["d1"],
                retry_interval=retry_interval,
                timeout=timeout,
            )

    asyncio.run(run())


def test_async_wait_for_command_result_retries(monkeypatch):
    now = [0.0]
    sleeps = []
    monkeypatch.setattr(commands.time, "monotonic", lambda: now[0])

    async def sleep(delay):
        sleeps.append(delay)
        now[0] += delay

    monkeypatch.setattr(commands.asyncio, "sleep", sleep)
    client = _AsyncCommandClient(
        [
            DeviceCommandResponse(status="queued"),
            DeviceCommandResponse(data=["done"]),
        ]
    )

    result = asyncio.run(
        commands.async_wait_for_command_result(
            client, "job", ["d1"], retry_interval=1, timeout=2
        )
    )
    assert result.data == ["done"]
    assert len(client.calls) == 2
    assert sleeps == [1]


def test_async_wait_for_command_result_can_be_cancelled(monkeypatch):
    monkeypatch.setattr(commands.time, "monotonic", lambda: 0.0)
    sleep_started = asyncio.Event()

    async def blocked_sleep(delay):
        sleep_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(commands.asyncio, "sleep", blocked_sleep)
    client = _AsyncCommandClient([DeviceCommandResponse(http_status_code=202)])

    async def run():
        task = asyncio.create_task(
            commands.async_wait_for_command_result(
                client, "job", ["d1"], retry_interval=1, timeout=5
            )
        )
        await sleep_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert len(client.calls) == 1
