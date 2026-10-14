# Implementation Plan: Chart Support

**Branch**: `feat/charts` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-chart-support/spec.md`

## Summary

Add `Chart` and `AsyncChart` as composition wrappers over the existing Applier classes. Explicit loading accepts tagged local directory, compressed tar archive, and repository sources. Chart obtains templates and effective values, prepares one Applier, and delegates inspection, previews, apply, delete, and recreation. Preserve CLI fixed index/branch constants, URL encoding, repository ordering, first matching version, first package URL, defaults replacement, and delete-before-apply behavior. Add native async acquisition with settled filesystem workers and safe temporary extraction. Keep existing platform clients, resource models, renderer, scheduler, and lifecycle results unchanged.

## Technical Context

**Language/Version**: Python 3.13+ as declared by `pyproject.toml`; explicitly select safe tar extraction behavior across supported patch versions.

**Primary Dependencies**: Existing HTTPX, PyYAML, Pydantic, Jinja2, and Ansible support; standard-library pathlib, tarfile, tempfile, asyncio, threading, urllib.parse, and warnings. No new runtime dependencies or lockfile change is expected. rio CLI is an explicit development oracle, never a runtime dependency.

**Storage**: Owned temporary extraction directories and checked-in workflow reference fixtures. Prepared charts retain in-memory metadata and the Applier's prepared collection, with no release database, persistent cache, or extracted-file lifetime.

**Testing**: pytest, pytest-asyncio, HTTPX MockTransport, controlled platform transports, malicious archive fixtures, tracked worker/transport cleanup checks, and existing six CLI-rendered chart fixtures. Ruff 0.16.9 lint/format gates.

**Target Platform**: Existing supported Python library platforms; local compressed tar preparation and remote HTTP(S) repository retrieval. No CLI installation or platform account is required for ordinary regression tests.

**Project Type**: Python SDK library with explicit fixture-capture tooling and executable validation examples.

**Performance Goals**: Asynchronous network and blocking preparation permit unrelated tasks to progress before completion. All acquisition workers and owned transport cleanup settle before cancellation returns. Preserve existing resource worker/readiness limits; add no speculative throughput or package-size target.

**Constraints**: Wrap both existing Applier classes; zero platform requests during local preparation/previews; exact call-time client ownership; first-entry/first-URL CLI behavior; hard-coded standard index and branch base; safe chart-root confinement; no automatic secret decryption. Owned acquisition clients use a finite 30-second HTTPX inactivity timeout; injected clients preserve caller timeout policy. Cancellation settlement waits for already-running local work to finish.

**Scale/Scope**: Three source kinds, paired repository workflows and Chart facades, the existing Apply resource coverage, 20 functional requirements, and nine success criteria. Verification includes two input sets each for postgis, gateway, and gostproxy. No new platform API operations, persistent install tracking, upgrades, rollback, chart publishing, or dependency-chart management.

## Constitution Check

*GATE: Passed before research; re-evaluated after Phase 1 design.*

| Principle | Gate and design evidence |
| --- | --- |
| I. Modern Python SDK | **Pass**. Typed source/inputs, paired factories/methods, metadata models, exceptions, and documented ownership/failures target Python 3.13+. See [chart-api.md](contracts/chart-api.md). |
| II. One-to-One API Clients | **Pass**. No methods added to or changed in `Client`/`AsyncClient`. Chart delegates platform operations to the existing Appliers. Acquisition HTTPX clients are separate and never receive platform credentials automatically. |
| III. Pydantic Contracts | **Pass**. New chart/index/entry/source models live in `models/chart.py`. Existing Pydantic `ApplierOptions`, `InspectionResult`, and `ApplierResult` remain the lifecycle contracts; all existing platform payload models and wire aliases are untouched. Rendering callbacks and inputs use a frozen runtime dataclass, not an API request payload. |
| IV. Separate Higher-Level Modules | **Pass**. Source packaging, repository retrieval, cancellation settlement, and delete-before-apply composition live in `chart/`. No orchestration enters client modules; no scheduler or resource lifecycle duplication is planned. |
| V. Ruff Compliance | **Pass, implementation gate**. Group render arguments in `ChartInputs` to meet argument limits, split acquisition/preparation helpers to meet complexity limits, and run pinned lint/format checks. No configuration relaxation is allowed. |

**Affected interfaces**: New Chart/AsyncChart loading and lifecycle methods, sync/async repository lookup methods, chart model/error exports, and package exports/documentation. Existing `ManifestSource`, `ApplierOptions`, `InspectionResult`, `ApplierResult`, resource methods, and clients are consumed unchanged. Platform request/response models and operations affected: none; Chart delegates the existing resource coverage in `specs/001-sdk-applier/spec.md`.

**Post-design review**: Explicit factories prevent hidden async I/O; one delegate preserves original result and source contracts; wrapper-level locking covers both recreation phases; source errors and optional exception notes avoid modifying Apply error classes. Native network cancellation and shielded local worker settlement satisfy async ownership. No constitutional exception or amendment is needed.

## Project Structure

### Documentation (this feature)

```text
specs/003-chart-support/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── chart-api.md
│   ├── repository-format.md
│   └── parity-validation.md
├── checklists/requirements.md
└── tasks.md                      # Produced later by $speckit-tasks
```

### Source Code (repository root)

```text
rapyuta_io_sdk_v2/
├── __init__.py                   # Public chart exports
├── models/
│   ├── __init__.py               # Chart metadata/source/index exports
│   └── chart.py                  # ChartSource, ChartMetadata, ChartEntry, ChartIndex
└── chart/
    ├── __init__.py               # Facades, helpers, inputs, errors, constants
    ├── chart.py                  # Chart and AsyncChart lifecycle composition
    ├── source.py                 # ChartInputs snapshot/normalization
    ├── repository.py             # ChartRepository/AsyncChartRepository and branch URL
    ├── errors.py                 # ChartError, ChartLoadError, ChartVersionWarning
    ├── _acquisition.py           # Index/package orchestration
    ├── _async.py                 # Tracked worker/cancellation settlement
    ├── _http.py                  # HTTPX ownership and body-free request errors
    └── _package.py               # Metadata/root validation, discovery, safe extraction

tests/chart/
├── __init__.py                 # Distinct pytest module identities
├── conftest.py                 # Controlled chart/transport fixtures
├── test_inspection.py          # Independent snapshots and source diagnostics
├── test_examples.py            # Runnable offline example commands
├── test_workflow_parity.py      # CLI decision comparisons
├── test_sources.py              # Tagged inputs, defaults, metadata, discovery
├── test_repository.py           # URL/order/lookup/ownership behavior
├── test_loading.py              # Directory/archive/repository equivalence and safety
├── test_lifecycle.py            # Delegation/recreation, scope, errors, phase snapshots
├── test_async.py                # Progress, cancellation, repeated cancellation
├── test_parity.py               # Six existing chart cases through both wrappers
├── test_capture_chart_workflow.py # Capture-tool provenance and replay
└── fixtures/                   # Controlled index/archive/workflow expectations

scripts/capture_apply_parity.py    # Chart-workflows capture/verify dispatch
scripts/chart_workflow_oracle.py   # Explicit CLI oracle; no runtime dependency
examples/chart/
├── sync_chart.py                 # Offline inspection/preview; optional live execution
└── async_chart.py                # Same usage through awaitable acquisition/execution
README.md                         # Chart guide and explicit secret-helper use
```

**Structure Decision**: Use a separate higher-level chart package and model module with dedicated tests. Reuse existing Apply code and frozen fixtures. No runtime changes to `apply/`, platform clients, resource models, `pyproject.toml`, or `uv.lock` are expected.

## Phase 0: Research

Completed [research.md](research.md) records decisions, evidence, and alternatives for source/input contracts, CLI repository semantics, HTTP transport ownership, safe extraction, eager cleanup, async settlement, recreation snapshots, and reference fixture capture. All initial technical unknowns are resolved. Two read-only research agents inspected acquisition/cancellation and wrapper/lifecycle composition.

## Phase 1: Design

Completed [data-model.md](data-model.md) specifies chart/source/index entities, runtime input snapshots, phase state, validation, and ownership. [chart-api.md](contracts/chart-api.md) fixes the public library interface; [repository-format.md](contracts/repository-format.md) fixes index/package compatibility and errors; [parity-validation.md](contracts/parity-validation.md) defines independent reference evidence. [quickstart.md](quickstart.md) describes validation after implementation, not functionality already delivered.

## Delivery Sequence

1. Define chart models, source factories, render input aggregation, errors/warning, and exports.
2. Implement local directory/archive preparation and the sync Chart facade with guarded recreation and original lifecycle results.
3. Add settled asynchronous local preparation and native AsyncChart lifecycle composition.
4. Capture independent CLI workflow expectations, then implement paired repository helpers, HTTPX ownership, branch/version/URL selection, and repository loading.
5. Complete public inspection/source diagnostics, both executable examples, and real-chart directory/archive comparisons.
6. Run focused/regression suites, pinned fixture replay, and Ruff checks; record actual evidence in tasks.md.

## Requirement Verification Map

| Requirements | Primary verification |
| --- | --- |
| FR-001–FR-003, FR-013 | Source equivalence, chart metadata/root validation, deterministic discovery, malicious member rejection and caller-file preservation. |
| FR-004–FR-005 | Defaults-only, explicit replacement including `{}`, ordered merge, secrets/rio/resolver inputs, existing filters and explicit SOPS use. |
| FR-006–FR-007, FR-009 | Existing Apply resource actions/results/errors, no client retention/closure, worker/readiness settings, retention, scope rebinding, preflight failures. |
| FR-008, FR-014 | Native async requests; progress during local preparation; settled threads/transports and zero owned temporary artifacts on cancellation/failure. |
| FR-010, FR-015 | Independent inspection, previews with no platform requests, preserved source-attributed validation and chart origin notes. |
| FR-011–FR-012, FR-017, FR-020 | Exact CLI index URL, branch encoding/precedence, entry ordering/lookup/listing, first package URL, metadata and error cases. |
| FR-016 | Documented examples runnable without rio for normal use; explicit optional fixture maintenance and live client setup. |
| FR-018–FR-019 | Both recreation phases and interruption snapshots, CLI workflow oracle, six existing CLI-rendered cases, scalar/document-order comparison. |

## Complexity Tracking

No constitutional violations. The small Chart operation guard protects a multi-phase workflow; the tracked-worker helper addresses a separate acquisition cancellation boundary. Neither replaces Apply scheduling or introduces another platform orchestration engine.
