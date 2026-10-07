"""Data returned by declarative operations; safe to import without extras."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ApplyError(Exception):
    """An invalid manifest, unsupported operation, or dependency graph."""


class ReadinessError(ApplyError):
    """A resource failed or did not become ready before its polling limit."""


class Outcome(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    EXISTS = "exists"
    DELETED = "deleted"
    RETAINED = "retained"
    NOT_FOUND = "not_found"
    PLANNED = "planned"
    FAILED = "failed"
    SKIPPED = "skipped"


class ResourceResult(BaseModel):
    identity: str
    outcome: Outcome
    resource: Any = None
    error: str | None = None


class ApplyPlan(BaseModel):
    operation: Literal["apply", "delete"]
    layers: list[list[str]]
    resources: list[Any]


class ApplyReport(BaseModel):
    operation: Literal["apply", "delete"]
    results: list[ResourceResult] = Field(default_factory=list)

    @property
    def successful(self) -> bool:
        return all(
            r.outcome not in (Outcome.FAILED, Outcome.SKIPPED) for r in self.results
        )

    def raise_for_errors(self) -> None:
        if not self.successful:
            raise ApplyExecutionError(self)


class ApplyExecutionError(ApplyError):
    """Failure retaining the full report for inspection or recovery."""

    def __init__(self, report: ApplyReport):
        self.report = report
        failures = [f"{r.identity}: {r.error}" for r in report.results if r.error]
        super().__init__("; ".join(failures) or "Operation did not complete")
