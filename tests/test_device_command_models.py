# Copyright 2026 Rapyuta Robotics
import pytest
from pydantic import ValidationError

from rapyuta_io_sdk_v2 import models


@pytest.mark.parametrize(
    "fields",
    [
        {"device_ids": []},
        {"device_ids": ["a", "a"]},
        {"device_ids": [" "]},
        {"cmd": " "},
        {"timeout": 0},
        {"timeout": float("inf")},
        {"bg": "true"},
        {"env": {"BAD-NAME": "a"}},
        {"env": {"KEY": 1}},
    ],
)
def test_invalid_command(fields: dict[str, object]) -> None:
    payload = {"device_ids": ["a"], "cmd": "true"} | fields
    with pytest.raises(ValidationError):
        models.DeviceCommand.model_validate(payload)


def test_command_preserves_text_and_empty_environment() -> None:
    body = models.DeviceCommand(
        device_ids=("a",), cmd="echo élite\nprintf ''", env={"EMPTY": ""}
    )
    assert body.cmd == "echo élite\nprintf ''"
    assert body.env["EMPTY"] == ""


def test_outputs_do_not_coerce() -> None:
    assert models.DeviceCommandOutputs({"a": ""}).root == {"a": ""}
    with pytest.raises(ValidationError):
        models.DeviceCommandOutputs({"a": 0})


@pytest.mark.parametrize("jid", ["", " ", "..", "a/b", "a\\b", "a\n"])
def test_invalid_job_identity(jid: str) -> None:
    with pytest.raises(ValidationError):
        models.DeviceCommandJob(jid=jid, minions=("a",))


@pytest.mark.parametrize("timeout", [True, "10", float("nan")])
def test_timeout_is_a_strict_finite_number(timeout: object) -> None:
    with pytest.raises(ValidationError):
        models.DeviceCommand(device_ids=("a",), cmd="true", timeout=timeout)
