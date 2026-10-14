# Copyright 2026 Rapyuta Robotics
"""Pure preparation and ordered command-progress bookkeeping."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from pydantic import ValidationError

from rapyuta_io_sdk_v2._device_api import command_payload, routing_id
from rapyuta_io_sdk_v2.exceptions import (
    DeviceCommandCancelled,
    DeviceCommandError,
    DeviceCommandTimeout,
    DeviceContractError,
)
from rapyuta_io_sdk_v2.models.device_command import (
    DeviceCommand,
    DeviceCommandDeviceResult,
    DeviceCommandFailure,
    DeviceCommandFailureStage,
    DeviceCommandJob,
    DeviceCommandOutcome,
    DeviceCommandOutputs,
    DeviceCommandResultQuery,
    DeviceCommandWaitOptions,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from rapyuta_io_sdk_v2.models.device_command import DeviceCommandSubmissionResponse


class CommandProgress:
    """Private mutable collection state; public snapshots are deeply immutable."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """Start with unknown remote acceptance.

        Args:
            clock: Monotonic clock used by the selected execution mode.
        """
        self.clock = clock
        self.requested: tuple[str, ...] = ()
        self.jid: str | None = None
        self.outputs: dict[str, str] = {}
        self.stage = DeviceCommandFailureStage.VALIDATION
        self.options = DeviceCommandWaitOptions()
        self.deadline = clock()

    def prepare(
        self, body: DeviceCommand, options: DeviceCommandWaitOptions | None
    ) -> DeviceCommand:
        """Copy/revalidate inputs and fill helper-only CLI defaults.

        Args:
            body: Caller command, never mutated.
            options: Caller local waiting options.
        """
        self._known_targets(body)
        self.options = DeviceCommandWaitOptions.model_validate(
            (options or DeviceCommandWaitOptions()).model_dump()
        )
        self.deadline = self.clock() + self.options.wait_timeout
        supplied = body.model_fields_set
        body = command_payload(body)
        if body.bg:
            message = "Background commands cannot be awaited for completion"
            raise ValueError(message)
        values = body.model_dump()
        if "shell" not in supplied:
            values["shell"] = "/bin/bash"
        if "runas" not in supplied:
            values["runas"] = "root"
        return DeviceCommand.model_validate(values)

    def _known_targets(self, body: DeviceCommand) -> None:
        try:
            self.requested = DeviceCommandResultQuery(
                device_ids=body.device_ids
            ).device_ids
        except (AttributeError, ValidationError):
            self.requested = ()

    def snapshot(self) -> DeviceCommandOutcome:
        """Return an ordered immutable copy of all acknowledged outputs."""
        return DeviceCommandOutcome(
            requested_devices=self.requested,
            jid=self.jid,
            responses=tuple(
                DeviceCommandDeviceResult(
                    device_guid=target, output=self.outputs[target]
                )
                for target in self.requested
                if target in self.outputs
            ),
            missing_devices=tuple(
                target for target in self.requested if target not in self.outputs
            ),
        )

    def error(
        self, kind: type[DeviceCommandError | DeviceCommandCancelled], message: str
    ) -> DeviceCommandError | DeviceCommandCancelled:
        """Pair error metadata with the same immutable progress snapshot.

        Args:
            kind: Public failure class.
            message: Redacted explanatory message.
        """
        result = self.snapshot()
        failure = DeviceCommandFailure(
            stage=self.stage,
            message=message,
            jid=result.jid,
            requested_devices=result.requested_devices,
            missing_devices=result.missing_devices,
        )
        return kind(failure, result)

    def remaining(self) -> float:
        """Refuse new work once the waiting budget is exhausted."""
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            self.stage = DeviceCommandFailureStage.TIMEOUT
            raise self.error(DeviceCommandTimeout, "Command waiting deadline expired")
        return remaining

    def pause(self) -> float:
        """Bound the next polling pause by remaining time."""
        return min(self.options.poll_interval, self.remaining())

    def query(self) -> DeviceCommandResultQuery:
        """Request only targets still missing, in original target order."""
        return DeviceCommandResultQuery(device_ids=self.snapshot().missing_devices)

    def acknowledge(
        self, response: DeviceCommandSubmissionResponse, body: DeviceCommand
    ) -> None:
        """Validate execution mode and exact accepted minions before polling.

        Args:
            response: Parsed command submission.
            body: Revalidated command sent once.
        """
        data = response.response.data.root
        self.stage = DeviceCommandFailureStage.CONTRACT
        if isinstance(data, DeviceCommandJob):
            routing_id(data.jid)
            self.jid = data.jid
            if (
                not body.run_async
                or len(data.minions) != len(self.requested)
                or set(data.minions) != set(self.requested)
            ):
                message = (
                    "Deferred acknowledgment does not match requested targets/mode"
                )
                raise DeviceContractError(message)
        elif body.run_async:
            message = "Deferred command returned immediate output"
            raise DeviceContractError(message)
        else:
            self.merge(data)
        self.remaining()
        if self.jid is None and self.snapshot().missing_devices:
            self.stage = DeviceCommandFailureStage.INCOMPLETE_RESULT
            raise self.error(
                DeviceCommandError, "Immediate result omitted requested devices"
            )

    def merge(self, outputs: DeviceCommandOutputs) -> None:
        """Preserve empty outputs and repeats; reject foreign/conflicting keys.

        Args:
            outputs: One immutable-to-the-caller result batch.
        """
        self.stage = DeviceCommandFailureStage.CONTRACT
        failure: DeviceContractError | None = None
        for target, value in outputs.root.items():
            try:
                self._accept(target, value)
            except DeviceContractError as error:
                if failure is None:
                    failure = error
        if failure is not None:
            raise failure

    def _accept(self, target: str, value: str) -> None:
        if target not in self.requested:
            message = "Command returned an unrequested device"
            raise DeviceContractError(message)
        if target in self.outputs and self.outputs[target] != value:
            message = "Command returned conflicting repeated output"
            raise DeviceContractError(message)
        self.outputs[target] = value

    def terminal(self, error: Exception) -> DeviceCommandError:
        """Wrap a terminal cause without exposing request secrets.

        Args:
            error: Original cause to chain at the call site.
        """
        if isinstance(error, DeviceContractError):
            if error.jid is not None:
                self.jid = error.jid
            self.stage = DeviceCommandFailureStage.CONTRACT
        return self.error(
            DeviceCommandError, f"Command {self.stage} failed ({type(error).__name__})"
        )
