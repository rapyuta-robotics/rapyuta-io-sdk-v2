# Copyright 2026 Rapyuta Robotics
from __future__ import annotations

import time
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

from rapyuta_io_sdk_v2 import Client, exceptions, models
from rapyuta_io_sdk_v2._device_api import command_submission
from rapyuta_io_sdk_v2.helpers import device
from rapyuta_io_sdk_v2.helpers._device_command import CommandProgress
from tests.data.device_data import COMMAND_JOB, COMMAND_PARTIAL_BATCHES, PENDING

WAIT_BUDGET = 0.01
DEFERRED_IDENTITY_CASES = (
    pytest.param(
        ({"jid": "command-output", "minions": ""}, ("jid", "minions"), None),
        id="requested-output-map",
    ),
    pytest.param(({"jid": "command-output"}, ("jid",), None), id="single-output"),
    pytest.param(({"jid": "known-job"}, ("a",), "known-job"), id="missing-minions"),
    pytest.param(
        ({"jid": "known-job", "minions": 42}, ("a",), "known-job"),
        id="malformed-minions",
    ),
)


def submission(data: object) -> models.DeviceCommandSubmissionResponse:
    return models.DeviceCommandSubmissionResponse.model_validate(
        {"status": "success", "response": {"data": data}}
    )


def output(data: object) -> models.DeviceCommandResultResponse:
    return models.DeviceCommandResultResponse.model_validate(
        {"status": "success", "response": {"data": data}}
    )


def command(*, deferred: bool = False) -> models.DeviceCommand:
    return models.DeviceCommand(
        device_ids=("a", "b", "c"), cmd="true", run_async=deferred
    )


def test_immediate_empty_output_and_owned_inputs() -> None:
    client = Mock(spec=Client)
    body = command()
    original = body.model_dump()
    client.execute_device_command.return_value = submission(
        {"a": "", "b": "b", "c": "c"}
    )
    result = device.execute_device_command(client, body)
    assert result.missing_devices == ()
    assert result.responses[0].output == ""
    assert body.model_dump() == original
    sent = client.execute_device_command.call_args.args[0]
    assert sent.shell == "/bin/bash"
    assert sent.runas == "root"
    client.get_device_command_result.assert_not_called()
    client.execute_device_command.assert_called_once()
    with pytest.raises(ValidationError):
        result.responses[0].output = "changed"


def test_staggered_deferred_collection() -> None:
    client = Mock(spec=Client)
    client.execute_device_command.return_value = (
        models.DeviceCommandSubmissionResponse.model_validate_json(COMMAND_JOB)
    )
    client.get_device_command_result.side_effect = [
        models.DeviceCommandResultResponse.model_validate_json(batch)
        for batch in COMMAND_PARTIAL_BATCHES
    ]
    result = device.execute_device_command(
        client,
        command(deferred=True),
        options=models.DeviceCommandWaitOptions(poll_interval=0.001),
    )
    assert tuple(item.device_guid for item in result.responses) == ("a", "b", "c")
    assert client.get_device_command_result.call_args_list[1].kwargs[
        "query"
    ].device_ids == ("a", "c")
    assert result.jid == "job"
    client.execute_device_command.assert_called_once()


@pytest.mark.parametrize("data", [{"a": ""}, {"a": "", "b": "b", "foreign": "x"}])
def test_immediate_failure_has_snapshot(data: dict[str, str]) -> None:
    client = Mock(spec=Client)
    client.execute_device_command.return_value = submission(data)
    with pytest.raises(exceptions.DeviceCommandError) as caught:
        device.execute_device_command(client, command())
    assert (
        caught.value.failure.requested_devices
        == caught.value.partial_result.requested_devices
    )
    assert (
        caught.value.failure.missing_devices
        == caught.value.partial_result.missing_devices
    )


def test_late_sync_result_is_timeout_with_all_outputs() -> None:
    client = Mock(spec=Client)

    def late(
        *_args: object, **_kwargs: object
    ) -> models.DeviceCommandSubmissionResponse:
        time.sleep(0.02)
        return submission({"a": "", "b": "b", "c": "c"})

    client.execute_device_command.side_effect = late
    with pytest.raises(exceptions.DeviceCommandTimeout) as caught:
        device.execute_device_command(
            client,
            command(),
            options=models.DeviceCommandWaitOptions(wait_timeout=0.005),
        )
    assert caught.value.partial_result.missing_devices == ()
    assert len(caught.value.partial_result.responses) == len(command().device_ids)
    assert caught.value.__cause__ is None
    client.get_device_command_result.assert_not_called()


def test_background_rejected_before_submission() -> None:
    client = Mock(spec=Client)
    with pytest.raises(exceptions.DeviceCommandError) as caught:
        device.execute_device_command(
            client, models.DeviceCommand(device_ids=("a",), cmd="true", bg=True)
        )
    assert caught.value.failure.stage == "validation"
    client.execute_device_command.assert_not_called()


@pytest.mark.parametrize(
    "batches",
    [[{"a": "first"}, {"a": "different"}], [{"a": "first"}, {"foreign": "x"}]],
)
def test_bad_later_batch_preserves_earlier_output(
    batches: list[dict[str, str]],
) -> None:
    client = Mock(spec=Client)
    client.execute_device_command.return_value = submission(
        {"jid": "job", "minions": ["a", "b", "c"]}
    )
    client.get_device_command_result.side_effect = [output(batch) for batch in batches]
    with pytest.raises(exceptions.DeviceCommandError) as caught:
        device.execute_device_command(
            client,
            command(deferred=True),
            options=models.DeviceCommandWaitOptions(poll_interval=0.001),
        )
    assert caught.value.failure.stage == "contract"
    assert caught.value.partial_result.responses[0].output == "first"
    assert caught.value.__cause__ is not None


def test_shorter_network_timeout_remains_terminal() -> None:
    client = Mock(spec=Client)
    cause = TimeoutError("short transport timeout")
    client.execute_device_command.return_value = submission(
        {"jid": "job", "minions": ["a", "b", "c"]}
    )
    client.get_device_command_result.side_effect = cause
    with pytest.raises(exceptions.DeviceCommandError) as caught:
        device.execute_device_command(client, command(deferred=True))
    assert caught.value.failure.stage == "retrieval"
    assert caught.value.__cause__ is cause
    assert caught.value.partial_result.jid == "job"
    client.get_device_command_result.assert_called_once()


def test_pending_timeout_starts_no_new_request() -> None:

    client = Mock(spec=Client)
    client.execute_device_command.return_value = submission(
        {"jid": "job", "minions": ["a", "b", "c"]}
    )
    client.get_device_command_result.return_value = (
        models.DeviceCommandPendingResponse.model_validate(PENDING)
    )
    with pytest.raises(exceptions.DeviceCommandTimeout) as caught:
        device.execute_device_command(
            client,
            command(deferred=True),
            options=models.DeviceCommandWaitOptions(wait_timeout=0.01, poll_interval=1),
        )
    assert caught.value.failure.jid == caught.value.partial_result.jid == "job"
    assert caught.value.failure.missing_devices == ("a", "b", "c")
    client.get_device_command_result.assert_called_once()
    assert (
        0
        < client.execute_device_command.call_args.kwargs["request_timeout"]
        <= WAIT_BUDGET
    )


def test_invalid_raw_input_context_has_empty_identities() -> None:
    client = Mock(spec=Client)
    with pytest.raises(exceptions.DeviceCommandError) as caught:
        device.execute_device_command(client, {})
    assert caught.value.failure.requested_devices == ()
    assert caught.value.partial_result.missing_devices == ()
    assert caught.value.failure.stage == "validation"


def test_malformed_acknowledgment_preserves_valid_job_id() -> None:

    client = Mock(spec=Client)

    def malformed(
        body: models.DeviceCommand, **_kwargs: object
    ) -> models.DeviceCommandSubmissionResponse:
        return command_submission(
            httpx.Response(
                200,
                json={"status": "success", "response": {"data": {"jid": "known-job"}}},
            ),
            body,
        )

    client.execute_device_command.side_effect = malformed
    with pytest.raises(exceptions.DeviceCommandError) as caught:
        device.execute_device_command(client, command(deferred=True))
    assert caught.value.failure.stage == "contract"
    assert caught.value.failure.jid == caught.value.partial_result.jid == "known-job"
    client.get_device_command_result.assert_not_called()


def test_identical_repeats_are_retained_and_default_inputs_are_unchanged() -> None:
    client = Mock(spec=Client)
    client.execute_device_command.return_value = submission(
        {"jid": "job", "minions": ["a", "b", "c"]}
    )
    client.get_device_command_result.side_effect = [
        output({"a": ""}),
        output({"a": "", "b": "ready", "c": "ready"}),
    ]
    body = command(deferred=True).model_copy(
        update={"shell": "fish", "runas": "operator", "cwd": "", "env": {"KEY": ""}}
    )
    original = body.model_dump()
    result = device.execute_device_command(
        client, body, options=models.DeviceCommandWaitOptions(poll_interval=0.001)
    )
    assert body.model_dump() == original
    assert client.execute_device_command.call_args.args[0].model_dump() == original
    assert result.responses[0].output == ""


def test_elapsed_requests_and_capped_pause_use_one_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock(spec=Client)
    now = [0.0]
    pauses: list[float] = []

    def submit(
        *_args: object, **_kwargs: object
    ) -> models.DeviceCommandSubmissionResponse:
        now[0] += 0.6
        return submission({"jid": "job", "minions": ["a", "b", "c"]})

    def retrieve(
        *_args: object, **_kwargs: object
    ) -> models.DeviceCommandPendingResponse:
        now[0] += 0.1
        return models.DeviceCommandPendingResponse.model_validate(PENDING)

    def sleep(duration: float) -> None:
        pauses.append(duration)
        now[0] += duration

    client.execute_device_command.side_effect = submit
    client.get_device_command_result.side_effect = retrieve
    monkeypatch.setattr(
        device, "CommandProgress", lambda: CommandProgress(lambda: now[0])
    )
    monkeypatch.setattr(device.time, "sleep", sleep)
    with pytest.raises(exceptions.DeviceCommandTimeout):
        device.execute_device_command(
            client,
            command(deferred=True),
            options=models.DeviceCommandWaitOptions(wait_timeout=1, poll_interval=10),
        )
    assert client.execute_device_command.call_args.kwargs["request_timeout"] == 1
    assert client.get_device_command_result.call_args.kwargs[
        "request_timeout"
    ] == pytest.approx(0.4)
    assert pauses == pytest.approx([0.3])
    client.get_device_command_result.assert_called_once()


def test_valid_late_lookup_retains_partial_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock(spec=Client)
    now = [0.0]

    def retrieve(
        *_args: object, **_kwargs: object
    ) -> models.DeviceCommandResultResponse:
        now[0] = 2.0
        return output({"a": ""})

    client.execute_device_command.return_value = submission(
        {"jid": "job", "minions": ["a", "b", "c"]}
    )
    client.get_device_command_result.side_effect = retrieve
    monkeypatch.setattr(
        device, "CommandProgress", lambda: CommandProgress(lambda: now[0])
    )
    with pytest.raises(exceptions.DeviceCommandTimeout) as caught:
        device.execute_device_command(
            client,
            command(deferred=True),
            options=models.DeviceCommandWaitOptions(wait_timeout=1),
        )
    assert caught.value.partial_result.responses[0].output == ""
    assert caught.value.failure.missing_devices == ("b", "c")
    client.get_device_command_result.assert_called_once()


def test_late_terminal_lookup_preserves_original_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock(spec=Client)
    now = [0.0]
    cause = exceptions.UnauthorizedAccessError("permission refused")

    def retrieve(*_args: object, **_kwargs: object) -> None:
        now[0] = 2.0
        raise cause

    client.execute_device_command.return_value = submission(
        {"jid": "job", "minions": ["a", "b", "c"]}
    )
    client.get_device_command_result.side_effect = retrieve
    monkeypatch.setattr(
        device, "CommandProgress", lambda: CommandProgress(lambda: now[0])
    )
    with pytest.raises(exceptions.DeviceCommandError) as caught:
        device.execute_device_command(
            client,
            command(deferred=True),
            options=models.DeviceCommandWaitOptions(wait_timeout=1),
        )
    assert caught.value.failure.stage == "retrieval"
    assert caught.value.__cause__ is cause


@pytest.mark.parametrize(
    "fields",
    [
        {"cmd": " "},
        {"device_ids": ()},
        {"timeout": float("inf")},
        {"env": {"BAD-NAME": "value"}},
    ],
)
def test_mutated_command_is_revalidated_before_submission(
    fields: dict[str, object],
) -> None:
    client = Mock(spec=Client)
    invalid = command().model_copy(update=fields)
    with pytest.raises(exceptions.DeviceCommandError) as caught:
        device.execute_device_command(client, invalid)
    assert caught.value.failure.stage == "validation"
    client.execute_device_command.assert_not_called()


@pytest.mark.parametrize(
    "minions", [["a", "b"], ["a", "a", "b"], ["a", "b", "foreign"]]
)
def test_deferred_ack_requires_exact_targets(minions: list[str]) -> None:
    client = Mock(spec=Client)
    client.execute_device_command.return_value = submission(
        {"jid": "job", "minions": minions}
    )
    with pytest.raises(exceptions.DeviceCommandError) as caught:
        device.execute_device_command(client, command(deferred=True))
    assert caught.value.failure.stage == "contract"
    assert caught.value.partial_result.jid == "job"
    client.get_device_command_result.assert_not_called()


def failure_batch(case: tuple[str, bool]) -> models.DeviceCommandResultResponse:
    key = "foreign" if case[0] == "foreign" else "a"
    bad = {key: "changed"}
    valid = {"b": ""}
    return output(bad | valid if case[1] else valid | bad)


@pytest.mark.parametrize(
    "case",
    [("foreign", True), ("foreign", False), ("conflict", True), ("conflict", False)],
)
def test_batch_failure_retains_all_valid_output(case: tuple[str, bool]) -> None:
    client = Mock(spec=Client)
    client.execute_device_command.return_value = (
        models.DeviceCommandSubmissionResponse.model_validate_json(COMMAND_JOB)
    )
    batches = [output({"a": "earlier"}), failure_batch(case)]
    client.get_device_command_result.side_effect = batches
    with pytest.raises(exceptions.DeviceCommandError) as caught:
        device.execute_device_command(
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
    client.execute_device_command.assert_called_once()
    assert client.get_device_command_result.call_count == len(batches)


@pytest.mark.parametrize("background", [False, True])
def test_real_client_mode_mismatch_retains_job(
    *, background: bool, client: Client
) -> None:
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

    client.c.close()
    body = models.DeviceCommand(device_ids=("a",), cmd="true", bg=background)
    with httpx.Client(transport=httpx.MockTransport(acknowledge)) as transport:
        client.c = transport
        if background:
            with pytest.raises(exceptions.DeviceContractError) as caught_direct:
                client.execute_device_command(body)
            assert caught_direct.value.jid == "known-job"
            assert isinstance(caught_direct.value.__cause__, ValidationError)
        else:
            with pytest.raises(exceptions.DeviceCommandError) as caught:
                device.execute_device_command(client, body)
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
        assert not client.c.is_closed


@pytest.mark.parametrize(
    "case",
    [
        ({"jid": "output", "minions": ""}, ("jid", "minions")),
        ({"jid": "output", "minions": 42}, ("a",)),
        ({"jid": "../bad", "minions": ["a"]}, ("a",)),
    ],
)
def test_real_client_output_keys_do_not_invent_job(
    case: tuple[dict[str, object], tuple[str, ...]], client: Client
) -> None:
    data, targets = case
    client.c.close()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, json={"status": "success", "response": {"data": data}}
            )
        )
    ) as transport:
        client.c = transport
        body = models.DeviceCommand(device_ids=targets, cmd="true")
        if isinstance(data["minions"], str):
            result = device.execute_device_command(client, body)
            assert result.jid is None
            assert [(item.device_guid, item.output) for item in result.responses] == [
                ("jid", "output"),
                ("minions", ""),
            ]
        else:
            with pytest.raises(exceptions.DeviceCommandError) as caught:
                device.execute_device_command(client, body)
            assert caught.value.failure.stage == "contract"
            assert caught.value.failure.jid is None


@pytest.mark.parametrize("case", DEFERRED_IDENTITY_CASES)
@pytest.mark.parametrize("via_helper", [False, True])
def test_real_client_deferred_failure_job_identity(
    case: tuple[dict[str, object], tuple[str, ...], str | None],
    *,
    via_helper: bool,
    client: Client,
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
    project = client.config.project_guid
    client.c.close()
    with httpx.Client(transport=httpx.MockTransport(acknowledge)) as transport:
        client.c = transport
        timeout = transport.timeout.as_dict()
        if via_helper:
            with pytest.raises(exceptions.DeviceCommandError) as caught:
                device.execute_device_command(client, body)
            assert_deferred_failure(caught.value, targets, known_job)
        else:
            with pytest.raises(exceptions.DeviceContractError) as caught_direct:
                client.execute_device_command(body)
            assert caught_direct.value.jid == known_job
            assert isinstance(caught_direct.value.__cause__, ValidationError)
        assert len(calls) == 1
        assert calls[0].method == "POST"
        assert body.model_dump() == original
        assert client.config.project_guid == project
        assert transport.timeout.as_dict() == timeout
        assert client.c is transport
        assert not transport.is_closed


def assert_deferred_failure(
    error: exceptions.DeviceCommandError,
    targets: tuple[str, ...],
    known_job: str | None,
) -> None:
    assert error.failure.stage == "contract"
    assert error.failure.jid == error.partial_result.jid == known_job
    assert (
        error.failure.requested_devices
        == error.partial_result.requested_devices
        == targets
    )
    assert (
        error.failure.missing_devices == error.partial_result.missing_devices == targets
    )
    assert error.partial_result.responses == ()
    assert isinstance(error.__cause__, exceptions.DeviceContractError)
    assert isinstance(error.__cause__.__cause__, ValidationError)
