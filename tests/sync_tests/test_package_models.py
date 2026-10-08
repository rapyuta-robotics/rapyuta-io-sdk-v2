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
