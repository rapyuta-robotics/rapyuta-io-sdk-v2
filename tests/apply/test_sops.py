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

"""Contract tests for explicit SOPS secret-file decryption."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import textwrap
import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from rapyuta_io_sdk_v2.apply.errors import SopsDecryptionError
from rapyuta_io_sdk_v2.apply.secrets import (
    async_decrypt_secret_file,
    decrypt_secret_file,
)
from rapyuta_io_sdk_v2.models.applier import SopsOptions

if TYPE_CHECKING:
    from collections.abc import Callable

    from rapyuta_io_sdk_v2.apply.source import JsonValue

_SYNC_NONZERO_EXIT = 23
_ASYNC_NONZERO_EXIT = 29
_MIN_HEARTBEATS = 3


def _executable(path: Path, body: str) -> Path:
    path.write_text(f"#!{sys.executable}\n" + textwrap.dedent(body))
    path.chmod(0o755)
    return path


def _source(path: Path, content: bytes = b"encrypted source bytes\n") -> Path:
    path.write_bytes(content)
    return path


def _assert_safe_error(error: SopsDecryptionError, secret: str) -> None:
    diagnostic = "".join(traceback.format_exception(error))
    assert secret not in str(error)
    assert secret not in repr(error)
    assert secret not in diagnostic
    assert secret not in error.guidance


@pytest.mark.parametrize(
    "case",
    [
        (".yaml", "yaml", '{"enabled":true,"items":[1,"two",null]}'),
        (".YML", "yaml", '{"enabled":true,"items":[1,"two",null]}'),
        (".JSON", "json", '{"enabled":true,"items":[1,"two",null]}'),
        (".yaml", "yaml", "{}"),
    ],
)
def test_sync_decrypts_yaml_and_json_with_literal_argv(
    tmp_path: Path,
    case: tuple[str, str, str],
) -> None:
    suffix, expected_type, output = case
    shell_marker = Path.cwd() / f"sops-{tmp_path.name}-injected"
    source = _source(
        tmp_path / f"-secret with spaces;$(touch {shell_marker.name}){suffix}"
    )
    expected = [
        "decrypt",
        "--input-type",
        expected_type,
        "--output-type",
        "json",
        str(source.resolve()),
    ]
    executable = _executable(
        tmp_path / "fake sops",
        f"""
        import json
        import sys
        expected = {expected!r}
        if sys.argv[1:] != expected:
            sys.stderr.write("unexpected argument vector")
            raise SystemExit(19)
        sys.stdout.write({output!r})
        """,
    )
    before = source.read_bytes()
    files_before = {item.name for item in tmp_path.iterdir()}

    result = decrypt_secret_file(
        source, options=SopsOptions(executable=str(executable))
    )

    assert result == json.loads(output)
    assert source.read_bytes() == before
    assert {item.name for item in tmp_path.iterdir()} == files_before
    assert not shell_marker.exists()


@pytest.mark.parametrize(
    "stdout",
    ["not-json", "null", "[]", '"scalar"', "17", "NaN", "Infinity"],
)
def test_sync_rejects_invalid_json_content_without_leaking_it(
    tmp_path: Path,
    fake_sops: Callable[..., Path],
    stdout: str,
) -> None:
    source = _source(tmp_path / "secrets.yaml")
    secret = "SENSITIVE-PLAINTEXT-7b2"
    executable = fake_sops(stdout=stdout.replace("SENSITIVE", secret))

    with pytest.raises(SopsDecryptionError) as raised:
        decrypt_secret_file(source, options=SopsOptions(executable=str(executable)))

    assert raised.value.category == "invalid_content"
    _assert_safe_error(raised.value, secret)


def test_sync_validates_source_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.yaml"
    with pytest.raises(SopsDecryptionError) as missing_error:
        decrypt_secret_file(missing)
    assert missing_error.value.category == "source"

    directory = tmp_path / "directory.yaml"
    directory.mkdir()
    with pytest.raises(SopsDecryptionError) as directory_error:
        decrypt_secret_file(directory)
    assert directory_error.value.category == "source"

    unsupported = _source(tmp_path / "secrets.txt")
    with pytest.raises(SopsDecryptionError) as unsupported_error:
        decrypt_secret_file(unsupported)
    assert unsupported_error.value.category == "source"

    unreadable = _source(tmp_path / "unreadable.json")
    real_access = os.access
    monkeypatch.setattr(
        os,
        "access",
        lambda path, mode: (
            False if Path(path) == unreadable else real_access(path, mode)
        ),
    )
    with pytest.raises(SopsDecryptionError) as unreadable_error:
        decrypt_secret_file(unreadable)
    assert unreadable_error.value.category == "source"


def test_sync_classifies_command_failures(
    tmp_path: Path, fake_sops: Callable[..., Path]
) -> None:

    source = _source(tmp_path / "secrets.yaml")
    with pytest.raises(SopsDecryptionError) as unavailable:
        decrypt_secret_file(
            source, options=SopsOptions(executable="missing-sops-command")
        )
    assert unavailable.value.category == "unavailable"

    secret = "CREDENTIAL-SECRET-1c4"
    executable = fake_sops(stdout=secret, stderr=secret, exit_code=_SYNC_NONZERO_EXIT)
    with pytest.raises(SopsDecryptionError) as decryption_error:
        decrypt_secret_file(source, options=SopsOptions(executable=str(executable)))
    assert decryption_error.value.category == "decryption"
    assert decryption_error.value.return_code == _SYNC_NONZERO_EXIT
    _assert_safe_error(decryption_error.value, secret)


@pytest.mark.asyncio
async def test_async_decryption_keeps_event_loop_responsive(
    tmp_path: Path, fake_sops: Callable[..., Path]
) -> None:
    source = _source(tmp_path / "slow.yaml")
    executable = fake_sops(stdout='{"ready":true}', delay=0.15)
    ticks = 0
    completed = asyncio.Event()

    async def decrypt() -> dict[str, JsonValue]:
        result = await async_decrypt_secret_file(
            source, options=SopsOptions(executable=str(executable))
        )
        completed.set()
        return result

    async def heartbeat() -> None:
        nonlocal ticks
        while not completed.is_set():
            await asyncio.sleep(0.01)
            ticks += 1

    result, _ = await asyncio.wait_for(
        asyncio.gather(decrypt(), heartbeat()), timeout=5
    )

    assert result == {"ready": True}
    assert ticks >= _MIN_HEARTBEATS


@pytest.mark.asyncio
async def test_async_errors_are_categorized_and_do_not_retain_command_output(
    tmp_path: Path, fake_sops: Callable[..., Path]
) -> None:
    source = _source(tmp_path / "async-secrets.yaml")
    secret = "ASYNC-CREDENTIAL-SECRET-42e"

    with pytest.raises(SopsDecryptionError) as unavailable:
        await async_decrypt_secret_file(
            source, options=SopsOptions(executable="missing-async-sops-command")
        )
    assert unavailable.value.category == "unavailable"

    failing = fake_sops(stdout=secret, stderr=secret, exit_code=_ASYNC_NONZERO_EXIT)
    with pytest.raises(SopsDecryptionError) as decryption:
        await async_decrypt_secret_file(
            source, options=SopsOptions(executable=str(failing))
        )
    assert decryption.value.category == "decryption"
    assert decryption.value.return_code == _ASYNC_NONZERO_EXIT
    _assert_safe_error(decryption.value, secret)

    malformed = fake_sops(stdout=f'{{"token": "{secret}",}}')
    with pytest.raises(SopsDecryptionError) as invalid:
        await async_decrypt_secret_file(
            source, options=SopsOptions(executable=str(malformed))
        )
    assert invalid.value.category == "invalid_content"
    _assert_safe_error(invalid.value, secret)


def _pid_is_running(pid: int, executable: Path) -> bool:
    """Check the original fake child, ignoring quick reuse of its PID."""
    command_line = Path(f"/proc/{pid}/cmdline")
    try:
        os.kill(pid, 0)
        return str(executable).encode() in command_line.read_bytes()
    except (FileNotFoundError, ProcessLookupError):
        return False


def _wait_for_file_sync(path: Path) -> None:
    deadline = time.monotonic() + 2.0
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.005)
    if not path.exists():
        message = "Child marker was not created"
        raise AssertionError(message)


async def _wait_for_file(path: Path) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 2.5
    while not path.exists():  # noqa: ASYNC240 — poll a local test marker file
        if loop.time() >= deadline:
            message = "Child marker was not created"
            raise AssertionError(message)
        await asyncio.sleep(0.005)


def _long_running_executable(tmp_path: Path, pid_file: Path) -> Path:
    return _executable(
        tmp_path / "long sops",
        f"""
        import os
        import signal
        import time
        from pathlib import Path
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        Path({str(pid_file)!r}).write_text(str(os.getpid()))
        print("SECRET-CHILD-OUTPUT", flush=True)
        while True:
            time.sleep(1)
        """,
    )


@pytest.mark.asyncio
async def test_async_cancellation_kills_ignoring_child_and_reaps_it(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path / "cancel.yaml")
    pid_file = tmp_path / "child.pid"
    executable = _long_running_executable(tmp_path, pid_file)
    task = asyncio.create_task(
        async_decrypt_secret_file(
            source,
            options=SopsOptions(executable=str(executable), termination_grace=0.03),
        )
    )
    await _wait_for_file(pid_file)
    child_pid = int(pid_file.read_text())
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert not _pid_is_running(child_pid, executable)


@pytest.mark.asyncio
async def test_async_cancellation_during_spawn_keeps_child_owned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path / "spawn.yaml")
    pid_file = tmp_path / "spawn-child.pid"
    executable = _long_running_executable(tmp_path, pid_file)
    real_spawn = asyncio.create_subprocess_exec
    spawned = asyncio.Event()
    release_spawn = asyncio.Event()

    async def delayed_spawn(
        *args: object, **kwargs: object
    ) -> asyncio.subprocess.Process:
        process = await real_spawn(*args, **kwargs)
        spawned.set()
        await release_spawn.wait()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed_spawn)
    task = asyncio.create_task(
        async_decrypt_secret_file(
            source,
            options=SopsOptions(executable=str(executable), termination_grace=0.03),
        )
    )
    await spawned.wait()
    await _wait_for_file(pid_file)
    child_pid = int(pid_file.read_text())
    task.cancel()
    asyncio.get_running_loop().call_later(0.02, release_spawn.set)

    with pytest.raises(asyncio.CancelledError):
        await task

    assert not _pid_is_running(child_pid, executable)


@pytest.mark.asyncio
async def test_async_repeated_cancellation_during_drain_still_reaps_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path / "drain.yaml")
    pid_file = tmp_path / "drain-child.pid"
    executable = _long_running_executable(tmp_path, pid_file)
    original_communicate = asyncio.subprocess.Process.communicate
    drain_started = asyncio.Event()
    release_drain = asyncio.Event()

    async def blocked_communicate(
        process: asyncio.subprocess.Process,
    ) -> tuple[bytes, bytes]:
        drain_started.set()
        await release_drain.wait()
        return await original_communicate(process)

    monkeypatch.setattr(asyncio.subprocess.Process, "communicate", blocked_communicate)
    task = asyncio.create_task(
        async_decrypt_secret_file(
            source,
            options=SopsOptions(executable=str(executable), termination_grace=0.03),
        )
    )
    await drain_started.wait()
    await _wait_for_file(pid_file)
    child_pid = int(pid_file.read_text())
    task.cancel()
    task.cancel()
    asyncio.get_running_loop().call_later(0.02, release_drain.set)

    with pytest.raises(asyncio.CancelledError):
        await task

    assert not _pid_is_running(child_pid, executable)


@pytest.mark.skipif(
    not hasattr(signal, "setitimer"), reason="requires POSIX interval timer"
)
def test_sync_keyboard_interrupt_settles_child(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path / "sync-interrupt.yaml")
    pid_file = tmp_path / "sync-child.pid"
    executable = _executable(
        tmp_path / "slow sync sops",
        f"""
        import os
        import time
        from pathlib import Path
        Path({str(pid_file)!r}).write_text(str(os.getpid()))
        while True:
            time.sleep(1)
        """,
    )
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)

    def interrupt(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGALRM, interrupt)
    signal.setitimer(signal.ITIMER_REAL, 0.1)
    try:
        with pytest.raises(KeyboardInterrupt):
            decrypt_secret_file(
                source,
                options=SopsOptions(executable=str(executable)),
            )
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)

    deadline = time.monotonic() + 2
    while not pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert pid_file.exists()
    assert not _pid_is_running(int(pid_file.read_text()), executable)
