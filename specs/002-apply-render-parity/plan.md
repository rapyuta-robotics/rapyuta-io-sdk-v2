# Implementation Plan: Apply Template Rendering Parity

**Branch**: `feat/apply` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-apply-render-parity/spec.md`

## Summary

Extend the existing SDK Applier's local rendering stage with the CLI's two rio filters and the five Ansible filter groups. Preserve template names and argument order, Jinja's built in `default`, SDK source attributed errors, and offline preparation. Supply device interface data through a caller owned resolver because the SDK has no device lookup API and parsing precedes client injection. Expose the parsed, pre-model manifest documents through inspection so tests can compare them directly with CLI parser output. Capture reproducible CLI fixtures from tracked postgis, gateway, and gostproxy templates using two distinct synthetic value sets per chart, then run SDK parity checks without a live account.

## Technical Context

**Language/Version**: Python 3.13+ per `pyproject.toml` and constitution.

**Primary Dependencies**: Existing Jinja2, PyYAML, Pydantic; add compatible `ansible-core` 2.21.x as a normal runtime dependency and update `uv.lock`. Fixture capture uses the sibling rio CLI only in tooling, never in SDK runtime imports. Match the CLI capture environment's resolved Ansible and Jinja versions to the SDK test environment and record both.

**Storage**: Checked in direct-filter cases and CLI output/failure fixtures, chart template copies, synthetic value sets, and provenance under `tests/apply/fixtures/parity/`; no database or remote storage.

**Testing**: pytest for filter contracts, rendering errors, sync/async inspection, chart parity, and capture-tool verification; CLI based fixture capture is a separate, explicit maintenance command. Ruff 0.16.9 lint and format gates.

**Target Platform**: Python library on platforms supported by the project; parity fixture generation needs a local rio CLI environment and checked out chart sources.

**Project Type**: Python SDK library with an offline fixture capture tool.

**Performance Goals**: The six chart cases finish as a local test suite without network I/O; rendering non-device manifests adds no device resolution calls.

**Constraints**: Preserve current `ManifestSource` and Applier construction flow, `StrictUndefined`, `ImmutableSandboxedEnvironment`, and caller owned clients. No live platform account or mutation in fixture tests. Source attributed failures occur before apply/delete. Fixture equality ignores YAML presentation while preserving document order and scalar types.

**Scale/Scope**: Two rio filters; five CLI registered Ansible filter groups; at least six cases covering all tracked templates in the three selected charts. Existing resource kinds and lifecycle rules stay in scope only for compatibility fixes needed to inspect the selected manifests.

## Constitution Check

*GATE: Passed before research and re-checked after design.*

| Principle | Plan and gate result |
|-----------|----------------------|
| I. Modern Python SDK | **Pass**. Public resolver and inspection additions will be typed, documented, and tested on Python 3.13+. |
| II. One-to-One API Clients | **Pass**. No Client or AsyncClient API operation changes. Device lookup/readiness remain caller supplied; no platform orchestration enters client modules. |
| III. Pydantic Request and Response Contracts | **Pass**. No platform API payload changes. The new inspection document is a Pydantic SDK model; existing API request/response models are untouched. |
| IV. Separate Higher-Level Modules | **Pass**. Filter registration, interface selection, and rendering stay in `rapyuta_io_sdk_v2/apply/`, outside client modules. |
| V. Ruff Compliance | **Pass, implementation gate**. Run the constitution's pinned Ruff check and format commands after changes. No rule or version relaxation is planned. |

**Post-design re-check**: The selected resolver contract avoids adding composite device operations to clients; `RenderedDocument` adds a typed higher-level inspection result rather than changing platform API models. No constitutional exception is required. During implementation, re-check runtime dependency compatibility, Pydantic serialization behavior, and Ruff results.

## Project Structure

### Documentation (this feature)

```text
specs/002-apply-render-parity/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── sdk-rendering.md
│   └── fixture-provenance.md
└── tasks.md                 # Created by $speckit-tasks, not this phase
```

### Source Code (repository root)

```text
rapyuta_io_sdk_v2/
├── apply/
│   ├── source.py            # Caller supplied interface resolver contract
│   ├── _filters.py          # Rio/Ansible filter registration and selection
│   ├── _loader.py           # Shared rendering and source-aware failures
│   └── applier.py           # Pass explicit scope; expose raw inspection documents
└── models/
    └── applier.py           # Typed RenderedDocument and InspectionResult addition

tests/apply/
├── test_loading.py          # Existing strict rendering behavior
├── test_filters.py          # Direct rio and Ansible contract coverage
├── test_chart_parity.py     # Six CLI fixture comparisons through both facades
├── test_capture_apply_parity.py # Offline capture-tool verification tests
└── fixtures/parity/
    ├── rio-filters/         # Direct rio cases, CLI outputs/errors, provenance
    ├── ansible-filters/     # Direct Ansible cases, CLI outputs, provenance
    ├── provenance.json      # Chart CLI/chart revisions and capture environment
    ├── postgis/             # Tracked chart template copies, two values, outputs
    ├── gateway/             # Tracked chart template copies, two values, outputs
    └── gostproxy/           # Tracked chart template copies, two values, outputs

scripts/
└── capture_apply_parity.py  # Explicit CLI oracle capture, never used by runtime

pyproject.toml                # Compatible Ansible runtime dependency
uv.lock                      # Resolved dependency set
```

**Structure Decision**: Reuse the current Apply package and its test directory. Store fixture inputs and outputs in this repository so ordinary tests do not require sibling repositories. The capture tool reads the pinned chart source and invokes the CLI parser only when fixtures are deliberately refreshed.

## Delivery Sequence

1. Add the version compatible Ansible dependency, shared filter registration point, and CLI fixture capture tool. Retain the existing sandbox and strict undefined mode.
2. Capture direct rio CLI outputs and the no-address failure before SDK assertions. Add the resolver contract to `ManifestSource`; thread `ApplierOptions.scope.project_guid` through shared preparation. Resolve candidate interface addresses in CLI order and report missing context or lookup failure as a source attributed template error. Keep calls synchronous at construction; an async user supplies an already available resolver or prefetches before construction.
3. Capture direct Ansible CLI outputs before SDK assertions, then register CLI groups in CLI order and skip Ansible's `default`.
4. Check in chart template copies and synthetic values. Capture expected documents with the rio CLI's local Apply parser, recording source revisions, dependency versions, environment, and controlled device response. Never derive expected documents from SDK output. Add a typed inspection field for deep copied parsed documents before model normalization; keep existing `resolved_manifests` unchanged.
5. Compare structured documents from sync and async SDK facades against each CLI fixture, replay expected CLI failures, test the capture tool offline, then run the full Apply suite and Ruff gates.

## Complexity Tracking

No constitutional violations or extra architectural layers are required.
