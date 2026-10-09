import pytest
from pydantic import ValidationError

from rapyuta_io_sdk_v2.models.package import Executable


def test_entrypoint_string_is_normalized_to_list():
    executable = Executable(entrypoint="/bin/sh")
    assert executable.entrypoint == ["/bin/sh"]


def test_run_as_bash_wraps_command_when_no_entrypoint():
    executable = Executable(command="echo hello", runAsBash=True)
    assert executable.command == ["/bin/bash", "-c", "echo hello"]


def test_run_as_bash_does_not_wrap_command_when_entrypoint_is_set():
    executable = Executable(
        entrypoint=["/bin/sh", "-c"],
        command="echo hello",
        runAsBash=True,
    )
    assert executable.entrypoint == ["/bin/sh", "-c"]
    assert executable.command == ["echo hello"]


def test_command_unwrapped_without_run_as_bash():
    executable = Executable(
        entrypoint=["/bin/sh", "-c"],
        command=["echo", "hello"],
    )
    assert executable.command == ["echo", "hello"]


def test_empty_entrypoint_is_unset_and_keeps_run_as_bash():
    for empty in ([], ""):
        executable = Executable(entrypoint=empty, command="echo hello", runAsBash=True)
        assert executable.entrypoint is None
        assert executable.command == ["/bin/bash", "-c", "echo hello"]


@pytest.mark.parametrize("entrypoint", ["/bin/sh -c", ["/bin/sh -c"]])
def test_entrypoint_with_spaces_in_path_is_rejected(entrypoint):
    with pytest.raises(ValidationError, match="executable path first"):
        Executable(entrypoint=entrypoint, command="echo hello")
