# Copyright 2026 Rapyuta Robotics
from __future__ import annotations

import asyncio
from itertools import pairwise
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from pydantic import ValidationError

from rapyuta_io_sdk_v2 import AsyncClient, exceptions, models
from rapyuta_io_sdk_v2.helpers import async_device
from tests.data.device_data import PENDING
from tests.helpers.test_device_command import (
    DEFERRED_IDENTITY_CASES,
    assert_deferred_failure,
    command,
    failure_batch,
    output,
    submission,
)

DEADLINE_TOLERANCE = 1.2
HEARTBEAT_MAX_GAP = 0.25


@pytest.mark.asyncio
async def test_async_deferred_empty_and_partial_outputs() -> None:
    client = Mock(spec=AsyncClient)
    client.execute_device_command = AsyncMock(
        return_value=submission({"jid": "job", "minions": ["a", "b", "c"]})
    )
    client.get_device_command_result = AsyncMock(
        side_effect=[output({"b": "b"}), output({"a": "", "c": "c"})]
    )
    result = await async_device.execute_device_command_async(
        client,
        command(deferred=True),
        options=models.DeviceCommandWaitOptions(poll_interval=0.001),
    )
    assert result.responses[0].output == ""
    assert result.missing_devices == ()
    client.execute_device_command.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("external", [True, False])
async def test_submission_cancellation_and_deadline(*, external: bool) -> None:
    client = Mock(spec=AsyncClient)

    async def slow(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(1)

    client.execute_device_command = AsyncMock(side_effect=slow)
    client.get_device_command_result = AsyncMock()
    task = asyncio.create_task(
        async_device.execute_device_command_async(
            client,
            command(),
            options=models.DeviceCommandWaitOptions(wait_timeout=0.03),
        )
    )
    if external:
        await asyncio.sleep(0.005)
        task.cancel()
    expected = (
        exceptions.DeviceCommandCancelled
        if external
        else exceptions.DeviceCommandTimeout
    )
    with pytest.raises(expected) as caught:
        await task
    assert caught.value.partial_result.jid is None
    assert caught.value.failure.requested_devices == ("a", "b", "c")
    client.get_device_command_result.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["retrieval", "sleep"])
async def test_cancellation_after_partial_results(phase: str) -> None:

    client = Mock(spec=AsyncClient)
    entered = asyncio.Event()

    async def retrieve(
        *_args: object, **_kwargs: object
    ) -> models.DeviceCommandResultResponse:
        if client.get_device_command_result.await_count == 1:
            if phase == "sleep":
                entered.set()
            return output({"a": ""})
        entered.set()
        await asyncio.sleep(1)
        return models.DeviceCommandPendingResponse.model_validate(PENDING)

    client.execute_device_command = AsyncMock(
        return_value=submission({"jid": "job", "minions": ["a", "b", "c"]})
    )
    client.get_device_command_result = AsyncMock(side_effect=retrieve)
    task = asyncio.create_task(
        async_device.execute_device_command_async(
            client,
            command(deferred=True),
            options=models.DeviceCommandWaitOptions(
                poll_interval=0.001 if phase == "retrieval" else 10
            ),
        )
    )
    await entered.wait()
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(exceptions.DeviceCommandCancelled) as caught:
        await task
    assert caught.value.partial_result.jid == "job"
    assert (
        caught.value.failure.missing_devices
        == caught.value.partial_result.missing_devices
    )
    assert caught.value.partial_result.responses[0].output == ""
    assert client.get_device_command_result.await_count == (
        2 if phase == "retrieval" else 1
    )
    assert task.cancelled()


@pytest.mark.asyncio
async def test_heartbeat_and_strict_async_deadline() -> None:
    client = Mock(spec=AsyncClient)

    async def slow(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(5)

    client.execute_device_command = AsyncMock(side_effect=slow)
    ticks: list[float] = []

    async def heartbeat() -> None:
        for _ in range(6):
            await asyncio.sleep(0.05)
            ticks.append(asyncio.get_running_loop().time())

    loop = asyncio.get_running_loop()
    start = loop.time()
    beat = asyncio.create_task(heartbeat())
    with pytest.raises(exceptions.DeviceCommandTimeout):
        await async_device.execute_device_command_async(
            client, command(), options=models.DeviceCommandWaitOptions(wait_timeout=0.2)
        )
    elapsed = loop.time() - start
    await beat
    assert elapsed < DEADLINE_TOLERANCE
    assert max(right - left for left, right in pairwise(ticks)) <= HEARTBEAT_MAX_GAP


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        (False, {"a": ""}, (), "incomplete_result"),
        (False, {"foreign": ""}, (), "contract"),
        (True, {"jid": "job", "minions": ["a", "b"]}, (), "contract"),
        (
            True,
            {"jid": "job", "minions": ["a", "b", "c"]},
            ({"a": "first"}, {"a": "different"}),
            "contract",
        ),
        (
            True,
            {"jid": "job", "minions": ["a", "b", "c"]},
            ({"a": "first"}, exceptions.UnauthorizedAccessError("permission denied")),
            "retrieval",
        ),
    ],
)
async def test_async_failure_stages_keep_matching_snapshots(
    case: tuple[bool, object, tuple[object, ...], str],
) -> None:
    deferred, data, batches, expected_stage = case
    client = Mock(spec=AsyncClient)
    client.execute_device_command = AsyncMock(return_value=submission(data))
    client.get_device_command_result = AsyncMock(
        side_effect=[
            batch if isinstance(batch, Exception) else output(batch)
            for batch in batches
        ]
    )
    with pytest.raises(exceptions.DeviceCommandError) as caught:
        await async_device.execute_device_command_async(
            client,
            command(deferred=deferred),
            options=models.DeviceCommandWaitOptions(poll_interval=0.001),
        )
    error = caught.value
    assert error.failure.stage == expected_stage
    for name in ("jid", "requested_devices", "missing_devices"):
        assert getattr(error.failure, name) == getattr(error.partial_result, name)
    if batches:
        assert error.partial_result.responses[0].output == "first"
        assert error.__cause__ is not None
    client.execute_device_command.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_short_transport_timeout_is_submission_failure() -> None:
    client = Mock(spec=AsyncClient)
    cause = TimeoutError("short network timeout")
    client.execute_device_command = AsyncMock(side_effect=cause)
    client.get_device_command_result = AsyncMock()
    with pytest.raises(exceptions.DeviceCommandError) as caught:
        await async_device.execute_device_command_async(client, command())
    assert caught.value.failure.stage == "submission"
    assert caught.value.failure.jid is None
    assert caught.value.__cause__ is cause
    client.get_device_command_result.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [("foreign", True), ("foreign", False), ("conflict", True), ("conflict", False)],
)
async def test_batch_failure_retains_all_valid_output(case: tuple[str, bool]) -> None:
    client = Mock(spec=AsyncClient)
    client.execute_device_command = AsyncMock(
        return_value=submission({"jid": "job", "minions": ["a", "b", "c"]})
    )
    batches = [output({"a": "earlier"}), failure_batch(case)]
    client.get_device_command_result = AsyncMock(side_effect=batches)
    with pytest.raises(exceptions.DeviceCommandError) as caught:
        await async_device.execute_device_command_async(
            client,
            command(deferred=True),
            options=models.DeviceCommandWaitOptions(poll_interval=0.001),
        )
    error = caught.value
    assert error.failure.stage == "contract"
    assert [
        (item.device_guid, item.output) for item in error.partial_result.responses
    ] == [("a", "earlier"), ("b", "")]
    assert (
        error.failure.missing_devices == error.partial_result.missing_devices == ("c",)
    )
    assert (
        error.failure.requested_devices
        == error.partial_result.requested_devices
        == ("a", "b", "c")
    )
    assert error.failure.jid == error.partial_result.jid == "job"
    assert isinstance(error.__cause__, exceptions.DeviceContractError)
    client.execute_device_command.assert_awaited_once()
    assert client.get_device_command_result.await_count == len(batches)


@pytest.mark.asyncio
async def test_real_client_mode_mismatch_retains_job(async_client: AsyncClient) -> None:
    calls: list[httpx.Request] = []

    def acknowledge(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "status": "success",
                "response": {"data": {"jid": "known-job", "minions": ["a"]}},
            },
        )

    await async_client.c.aclose()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(acknowledge)
    ) as transport:
        async_client.c = transport
        with pytest.raises(exceptions.DeviceCommandError) as caught:
            await async_device.execute_device_command_async(
                async_client, models.DeviceCommand(device_ids=("a",), cmd="true")
            )
        error = caught.value
        assert error.failure.stage == "contract"
        assert error.failure.jid == error.partial_result.jid == "known-job"
        assert (
            error.failure.missing_devices
            == error.partial_result.missing_devices
            == ("a",)
        )
        assert error.partial_result.responses == ()
        assert isinstance(error.__cause__, exceptions.DeviceContractError)
        assert isinstance(error.__cause__.__cause__, ValidationError)
        assert len(calls) == 1
        assert calls[0].method == "POST"
        assert not async_client.c.is_closed
    async_client.sync_client.close()


@pytest.mark.asyncio
async def test_real_client_output_keys_do_not_invent_job(
    async_client: AsyncClient,
) -> None:
    await async_client.c.aclose()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "status": "success",
                    "response": {"data": {"jid": "output", "minions": ""}},
                },
            )
        )
    ) as transport:
        async_client.c = transport
        result = await async_device.execute_device_command_async(
            async_client,
            models.DeviceCommand(device_ids=("jid", "minions"), cmd="true"),
        )
        assert result.jid is None
        assert [(item.device_guid, item.output) for item in result.responses] == [
            ("jid", "output"),
            ("minions", ""),
        ]
    async_client.sync_client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", DEFERRED_IDENTITY_CASES)
@pytest.mark.parametrize("via_helper", [False, True])
async def test_real_client_deferred_failure_job_identity(
    case: tuple[dict[str, object], tuple[str, ...], str | None],
    *,
    via_helper: bool,
    async_client: AsyncClient,
) -> None:
    data, targets, known_job = case
    calls: list[httpx.Request] = []

    def acknowledge(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, json={"status": "success", "response": {"data": data}}
        )

    body = models.DeviceCommand(device_ids=targets, cmd="true", run_async=True)
    original = body.model_dump()
    project = async_client.config.project_guid
    await async_client.c.aclose()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(acknowledge)
    ) as transport:
        async_client.c = transport
        timeout = transport.timeout.as_dict()
        if via_helper:
            with pytest.raises(exceptions.DeviceCommandError) as caught:
                await async_device.execute_device_command_async(async_client, body)
            assert_deferred_failure(caught.value, targets, known_job)
        else:
            with pytest.raises(exceptions.DeviceContractError) as caught_direct:
                await async_client.execute_device_command(body)
            assert caught_direct.value.jid == known_job
            assert isinstance(caught_direct.value.__cause__, ValidationError)
        assert len(calls) == 1
        assert calls[0].method == "POST"
        assert body.model_dump() == original
        assert async_client.config.project_guid == project
        assert transport.timeout.as_dict() == timeout
        assert async_client.c is transport
        assert not transport.is_closed
    async_client.sync_client.close()
