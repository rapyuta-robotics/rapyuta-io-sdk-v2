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

"""Documented examples return their failure exit code with partial outcomes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from examples.applier import async_apply, sync_apply
from rapyuta_io_sdk_v2.apply.errors import ApplierExecutionError
from rapyuta_io_sdk_v2.models.applier import (
    ApplierResult,
    OperationFailure,
    ResourceIdentity,
    ResourceOutcome,
)

if TYPE_CHECKING:
    import pytest


def _execution_error() -> ApplierExecutionError:
    failure = OperationFailure(
        category="rejected", stage="apply", message="request was rejected"
    )
    result = ApplierResult(
        operation="apply",
        outcomes=(
            ResourceOutcome(
                identity=ResourceIdentity(kind="role", name="viewer"),
                operation="apply",
                status="failed",
                failure=failure,
            ),
        ),
    )
    return ApplierExecutionError("apply failed", result=result, causes=(failure,))


def test_sync_example_reports_failure_identity_and_returns_failure_status(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    error = _execution_error()

    class FailingApplier:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def apply(self, _client: object) -> object:
            raise error

    client = SimpleNamespace(c=SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(
        sync_apply,
        "Configuration",
        SimpleNamespace(from_file=lambda _path: object()),
    )
    monkeypatch.setattr(sync_apply, "Client", lambda _config: client)
    monkeypatch.setattr(sync_apply, "Applier", FailingApplier)

    status = sync_apply.main(["--config", "config", "--manifest", "manifest.yml"])

    output = capsys.readouterr().out
    assert status == 1
    assert "role: failed" in output
    assert "role: rejected" in output


def test_async_example_reports_failure_identity_and_returns_failure_status(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    error = _execution_error()

    class FailingApplier:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def apply(self, _client: object) -> object:
            raise error

    async def close_async() -> None:
        return None

    client = SimpleNamespace(
        c=SimpleNamespace(aclose=close_async),
        sync_client=SimpleNamespace(close=lambda: None),
    )
    monkeypatch.setattr(
        async_apply,
        "Configuration",
        SimpleNamespace(from_file=lambda _path: object()),
    )
    monkeypatch.setattr(async_apply, "AsyncClient", lambda _config: client)
    monkeypatch.setattr(async_apply, "AsyncApplier", FailingApplier)

    status = async_apply.main(["--config", "config", "--manifest", "manifest.yml"])

    output = capsys.readouterr().out
    assert status == 1
    assert "role: failed" in output
    assert "role: rejected" in output
