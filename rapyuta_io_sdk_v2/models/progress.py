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

"""Typed, per-resource mutation progress snapshots."""

from __future__ import annotations

from threading import Lock
from typing import Literal

from pydantic import ConfigDict, Field, StrictInt

from rapyuta_io_sdk_v2.models.base import SDKModel

MutationAction = Literal["created", "updated", "deleted", "revoked"]
MutationState = Literal["started", "completed", "rejected", "uncertain"]


class MutationAttempt(SDKModel):
    """Immutable state for one platform write attempt."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    sequence: StrictInt = Field(gt=0)
    action: MutationAction
    state: MutationState


class MutationJournal:
    """Record one pending platform write and expose detached snapshots."""

    __slots__ = ("_attempts", "_lock", "_next_sequence", "_pending")

    def __init__(self) -> None:
        """Create an empty journal with no pending write."""
        self._attempts: list[MutationAttempt] = []
        self._next_sequence = 1
        self._pending: int | None = None
        self._lock = Lock()

    def begin(self, action: MutationAction) -> int:
        """Start a write attempt and return its monotonically increasing ID."""
        with self._lock:
            if self._pending is not None:
                msg = "a write attempt is already pending"
                raise RuntimeError(msg)
            attempt = MutationAttempt(
                sequence=self._next_sequence, action=action, state="started"
            )
            self._attempts.append(attempt)
            self._pending = self._next_sequence
            self._next_sequence += 1
            return attempt.sequence

    def complete(self, sequence: int) -> None:
        """Mark a validated successful write as complete."""
        self._transition(sequence, "completed")

    def reject(self, sequence: int) -> None:
        """Mark a documented no-effect write rejection."""
        self._transition(sequence, "rejected")

    def mark_uncertain(self, sequence: int) -> None:
        """Mark a write whose platform effect cannot be confirmed."""
        self._transition(sequence, "uncertain")

    def snapshot(self) -> tuple[MutationAttempt, ...]:
        """Return an immutable copy of all attempts recorded so far."""
        with self._lock:
            return tuple(self._attempts)

    def _transition(self, sequence: int, state: MutationState) -> None:
        with self._lock:
            if type(sequence) is not int or self._pending != sequence:
                msg = "sequence is unknown or is not the pending write"
                raise RuntimeError(msg)
            current = self._attempts[-1]
            if current.sequence != sequence or current.state != "started":
                msg = "write attempt has already reached a terminal state"
                raise RuntimeError(msg)
            self._attempts[-1] = current.model_copy(update={"state": state})
            self._pending = None
