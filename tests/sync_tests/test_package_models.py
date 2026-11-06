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

from rapyuta_io_sdk_v2.models.package import Executable


def test_entrypoint_string_is_normalized_to_list() -> None:
    executable = Executable(entrypoint="/bin/sh")
    assert executable.entrypoint == ["/bin/sh"]


def test_run_as_bash_wraps_command_when_no_entrypoint() -> None:
    executable = Executable(command="echo hello", runAsBash=True)
    assert executable.command == ["/bin/bash", "-c", "echo hello"]


def test_run_as_bash_does_not_wrap_command_when_entrypoint_is_set() -> None:
    executable = Executable(
        entrypoint=["/bin/sh", "-c"],
        command="echo hello",
        runAsBash=True,
    )
    assert executable.entrypoint == ["/bin/sh", "-c"]
    assert executable.command == ["echo hello"]


def test_command_unwrapped_without_run_as_bash() -> None:
    executable = Executable(
        entrypoint=["/bin/sh", "-c"],
        command=["echo", "hello"],
    )
    assert executable.command == ["echo", "hello"]


def test_empty_entrypoint_is_unset_and_keeps_run_as_bash() -> None:
    for empty in ([], ""):
        executable = Executable(entrypoint=empty, command="echo hello", runAsBash=True)
        assert executable.entrypoint is None
        assert executable.command == ["/bin/bash", "-c", "echo hello"]
