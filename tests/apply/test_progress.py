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

"""Mutation journal and runtime context contract tests."""

import pytest
from pydantic import ValidationError

from rapyuta_io_sdk_v2.models.applier import (
    ApplierOptions,
    ApplierResult,
    ReadinessOptions,
    ResourceContext,
    ResourceIdentity,
    ResourceOutcome,
    ResourceReference,
    ResourceScope,
)
from rapyuta_io_sdk_v2.models.base import SDKModel
from rapyuta_io_sdk_v2.models.progress import MutationAttempt, MutationJournal


def test_journal_sequences_and_terminal_transitions() -> None:
    journal = MutationJournal()
    assert journal.snapshot() == ()

    created = journal.begin("created")
    journal.complete(created)
    updated = journal.begin("updated")
    journal.reject(updated)
    uncertain = journal.begin("deleted")
    journal.mark_uncertain(uncertain)

    assert [attempt.sequence for attempt in journal.snapshot()] == [1, 2, 3]
    assert [attempt.state for attempt in journal.snapshot()] == [
        "completed",
        "rejected",
        "uncertain",
    ]


def test_snapshot_is_detached_and_attempts_are_frozen() -> None:
    journal = MutationJournal()
    sequence = journal.begin("created")
    before = journal.snapshot()
    journal.complete(sequence)

    assert before[0].state == "started"
    assert journal.snapshot()[0].state == "completed"
    with pytest.raises(ValidationError):
        MutationAttempt(sequence=True, action="created", state="started")
    with pytest.raises(ValidationError):
        MutationAttempt(sequence=0, action="created", state="started")
    with pytest.raises(ValidationError):
        before[0].state = "completed"


def test_programmer_errors_are_rejected_before_another_write() -> None:
    journal = MutationJournal()
    sequence = journal.begin("created")
    with pytest.raises(RuntimeError, match="already pending"):
        journal.begin("updated")
    with pytest.raises(RuntimeError, match="unknown"):
        journal.complete(sequence + 1)
    with pytest.raises(RuntimeError, match="unknown"):
        journal.complete(sequence=True)

    journal.complete(sequence)
    with pytest.raises(RuntimeError, match="unknown"):
        journal.reject(sequence)


def test_context_retains_exact_recorder_but_excludes_it_from_serialization() -> None:
    journal = MutationJournal()
    context = ResourceContext(progress=journal)

    assert context.progress is journal
    assert "progress" not in context.model_dump()
    assert "progress" not in context.model_dump_json()
    assert "progress" not in repr(context)
    for mode in ("validation", "serialization"):
        assert "progress" not in str(ResourceContext.model_json_schema(mode=mode))
    assert SDKModel.model_config.get("arbitrary_types_allowed") is not True


def test_options_and_identity_models_keep_the_documented_constraints() -> None:
    options = ApplierOptions()
    expected_workers = 6
    assert options.workers == expected_workers
    assert options.readiness == ReadinessOptions(checks=50, interval=6.0)
    assert options.readiness is not ApplierOptions().readiness
    assert options.scope is not ApplierOptions().scope
    assert ReadinessOptions(checks=1, interval=0).interval == 0

    with pytest.raises(ValidationError):
        ReadinessOptions(checks=True)
    with pytest.raises(ValidationError):
        ReadinessOptions(interval=float("inf"))
    with pytest.raises(ValidationError):
        ApplierOptions(workers=False)
    with pytest.raises(ValidationError):
        ResourceScope(organization_guid="")
    with pytest.raises(ValidationError):
        ResourceReference(kind="package", name="app", version="")

    reference = ResourceReference(kind="Package", name="  app@prod  ", version="v:1")
    assert reference.kind == "package"
    assert reference.name == "  app@prod  "
    assert hash(reference)


def test_result_success_tracks_successful_statuses_and_plans() -> None:
    identity = ResourceReference(kind="role", name="viewer")
    role_identity = ResourceIdentity(kind="role", name=identity.name)
    planned = ResourceOutcome(
        identity=role_identity,
        operation="apply",
        status="planned",
        planned_action="create_or_update",
    )
    assert ApplierResult(
        operation="apply", dry_run=True, outcomes=(planned,)
    ).successful

    failed = planned.model_copy(update={"status": "failed"})
    assert not ApplierResult(operation="apply", outcomes=(failed,)).successful
