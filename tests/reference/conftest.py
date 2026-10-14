# Copyright 2026 Rapyuta Robotics

"""Mandatory provenance, execution and zero-skip gate for the real consumer."""

from __future__ import annotations

import json
from importlib.metadata import distribution

import httpx
import pytest
import requests

REVISION = "739a6fe44600ff0964fa56b04878ddb21e76b5be"
REPORTS: list[pytest.TestReport] = []


def pytest_configure() -> None:
    """Reject an absent SDK or any installation outside the pinned revision."""
    provenance = json.loads(
        distribution("rapyuta-io").read_text("direct_url.json") or "{}"
    )
    if provenance.get("vcs_info", {}).get("commit_id") != REVISION:
        message = "Reference SDK must be installed from the pinned git revision"
        raise pytest.UsageError(message)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Retain required case outcomes, including skips in any execution phase."""
    if "tests/reference/" in report.nodeid:
        REPORTS.append(report)


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Make empty execution or skipped required cases fail the test command."""
    executed = any(report.when == "call" for report in REPORTS)
    if not executed or any(report.skipped for report in REPORTS):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture
def device_reference_network_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject real I/O only for Device reference cases opting into this fixture."""

    def reject_network(*_args: object, **_kwargs: object) -> None:
        message = "Device reference checks must not use live network transports"
        raise AssertionError(message)

    monkeypatch.setattr(requests.sessions.Session, "send", reject_network)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", reject_network)
    monkeypatch.setattr(
        httpx.AsyncHTTPTransport, "handle_async_request", reject_network
    )
