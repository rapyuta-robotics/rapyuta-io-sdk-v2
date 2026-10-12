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

"""Explicit helpers for decrypting SOPS secret-value files."""

from __future__ import annotations

import asyncio
import json
import math
import os
import stat
import subprocess
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, cast

from rapyuta_io_sdk_v2.apply.errors import SopsDecryptionError
from rapyuta_io_sdk_v2.models.applier import SopsOptions

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.apply.source import JsonValue, PathInput

_GUIDANCE = {
    "unavailable": "Install SOPS and ensure the executable is available on PATH.",
    "source": "Correct the input file path, permissions, or YAML/JSON extension.",
    "decryption": "Check local SOPS configuration and key-provider setup.",
    "invalid_content": "Supply a valid YAML/JSON secret-values mapping.",
}


def _failure(
    source: PathInput,
    category: str,
    *,
    return_code: int | None = None,
) -> SopsDecryptionError:
    return SopsDecryptionError(
        source,
        category=category,
        return_code=return_code,
        guidance=_GUIDANCE[category],
    )


def _resolve_source(path: PathInput) -> tuple[Path, str]:
    """Resolve and validate one readable regular YAML/JSON source file."""
    try:
        resolved = Path(path).expanduser().resolve(strict=True)
        file_stat = resolved.stat()
    except (OSError, RuntimeError, ValueError):
        raise _failure(path, "source") from None

    suffix = resolved.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        input_type = "yaml"
    elif suffix == ".json":
        input_type = "json"
    else:
        raise _failure(path, "source") from None

    if not stat.S_ISREG(file_stat.st_mode) or not os.access(resolved, os.R_OK):
        raise _failure(path, "source") from None
    return resolved, input_type


def _is_json_value(value: object) -> bool:
    """Return whether a decoded value uses only finite JSON value types."""
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    return isinstance(value, Mapping) and all(
        isinstance(key, str) and _is_json_value(item) for key, item in value.items()
    )


def _reject_constant(_value: str) -> NoReturn:
    """Reject the non-standard NaN and Infinity tokens accepted by json."""
    message = "Invalid JSON constant"
    raise ValueError(message)


def _decode_mapping(output: bytes, source: PathInput) -> dict[str, JsonValue]:
    """Decode strict JSON and require a string-keyed mapping at the root."""
    try:
        decoded = json.loads(output.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, TypeError, RecursionError):
        raise _failure(source, "invalid_content") from None
    try:
        valid_mapping = isinstance(decoded, dict) and _is_json_value(decoded)
    except RecursionError:
        valid_mapping = False
    if not valid_mapping:
        raise _failure(source, "invalid_content") from None
    return cast("dict[str, JsonValue]", decoded)


def _command(executable: str, input_type: str, source: Path) -> list[str]:
    return [
        executable,
        "decrypt",
        "--input-type",
        input_type,
        "--output-type",
        "json",
        str(source),
    ]


def decrypt_secret_file(
    path: PathInput,
    *,
    options: SopsOptions | None = None,
) -> dict[str, JsonValue]:
    """Decrypt a YAML/JSON file with SOPS and return a JSON values mapping.

    SOPS is invoked explicitly with a literal argument vector. Encrypted input
    is passed by path and is never copied to a plaintext temporary file.
    """
    selected = options or SopsOptions()
    source, input_type = _resolve_source(path)
    try:
        completed = subprocess.run(  # noqa: S603 — literal argv, no shell
            _command(selected.executable, input_type, source),
            capture_output=True,
            check=False,
        )
    except OSError:
        raise _failure(path, "unavailable") from None

    if completed.returncode != 0:
        raise _failure(path, "decryption", return_code=completed.returncode) from None
    return _decode_mapping(completed.stdout, path)


async def _await_uncancelled[T](task: asyncio.Task[T]) -> T:
    """Wait for an owned task despite any further caller cancellations."""
    while True:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.done():
                return task.result()


def _streams_are_drained(process: asyncio.subprocess.Process) -> bool:
    return (process.stdout is None or process.stdout.at_eof()) and (
        process.stderr is None or process.stderr.at_eof()
    )


def _terminate(process: asyncio.subprocess.Process) -> None:
    with suppress(ProcessLookupError):
        process.terminate()


def _kill(process: asyncio.subprocess.Process) -> None:
    with suppress(ProcessLookupError):
        process.kill()


async def _await_drain(
    process: asyncio.subprocess.Process,
    drain_task: asyncio.Task[tuple[bytes, bytes]],
) -> None:
    while not drain_task.done():
        await asyncio.wait({drain_task}, timeout=0.05)
        if process.returncode is not None and _streams_are_drained(process):
            # Some loop transports leave wait() pending after exit and EOF.
            # At this point the child is reaped and all captured bytes drained.
            await process.wait()
            drain_task.cancel()
            with suppress(asyncio.CancelledError):
                await drain_task
            return

    try:
        await drain_task
    except OSError:
        # Settle the child if pipe draining failed, then discard its output.
        if process.returncode is None:
            _kill(process)
            await process.wait()


async def _terminate_and_drain(
    process: asyncio.subprocess.Process,
    communicate_task: asyncio.Task[tuple[bytes, bytes]] | None,
    grace: float,
) -> None:
    """Terminate a child, escalating after grace and draining its captured pipes."""
    drain_task = communicate_task or asyncio.create_task(process.communicate())
    if process.returncode is None:
        _terminate(process)
    done, _ = await asyncio.wait({drain_task}, timeout=grace)
    if not done and process.returncode is None:
        _kill(process)
    await _await_drain(process, drain_task)


async def _cleanup_uncancelled(
    process: asyncio.subprocess.Process,
    communicate_task: asyncio.Task[tuple[bytes, bytes]] | None,
    grace: float,
) -> None:
    cleanup_task = asyncio.create_task(
        _terminate_and_drain(process, communicate_task, grace)
    )
    await _await_uncancelled(cleanup_task)


async def _spawn_owned(
    argv: list[str],
    source: PathInput,
    grace: float,
) -> asyncio.subprocess.Process:
    spawn_task = asyncio.create_task(
        asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    )
    try:
        return await asyncio.shield(spawn_task)
    except asyncio.CancelledError:
        try:
            process = await _await_uncancelled(spawn_task)
        except (OSError, asyncio.CancelledError):
            raise asyncio.CancelledError from None
        await _cleanup_uncancelled(process, None, grace)
        raise
    except OSError:
        raise _failure(source, "unavailable") from None


async def async_decrypt_secret_file(
    path: PathInput,
    *,
    options: SopsOptions | None = None,
) -> dict[str, JsonValue]:
    """Asynchronously decrypt a YAML/JSON file with native subprocess I/O."""
    selected = options or SopsOptions()
    source, input_type = _resolve_source(path)
    process = await _spawn_owned(
        _command(selected.executable, input_type, source),
        path,
        selected.termination_grace,
    )

    communicate_task = asyncio.create_task(process.communicate())
    try:
        stdout, _stderr = await asyncio.shield(communicate_task)
    except asyncio.CancelledError:
        await _cleanup_uncancelled(
            process, communicate_task, selected.termination_grace
        )
        raise
    except OSError:
        await _cleanup_uncancelled(
            process, communicate_task, selected.termination_grace
        )
        raise _failure(path, "decryption", return_code=process.returncode) from None

    if process.returncode != 0:
        raise _failure(path, "decryption", return_code=process.returncode) from None
    return _decode_mapping(stdout, path)


__all__ = ["async_decrypt_secret_file", "decrypt_secret_file"]
