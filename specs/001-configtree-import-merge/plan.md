# Implementation Plan: Configtree Import and Fast Merge

**Branch**: `feat/configtrees` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-configtree-import-merge/spec.md`

## Summary

Provide synchronous and asynchronous Import and non-interactive fast Merge as separate SDK helpers composing the existing clients. Import prepares all files before mutation, splits rio-compatible metadata wrappers, flattens content under filename stems, and stages typed key values. `Revision` and `AsyncRevision` expose a live editable `keys` dictionary; normal exit validates an independent snapshot, performs one batch write when nonempty, and optionally commits. Workflows select the head only after successful finalization.

Merge resolves the source refspec in its own scope, compares exact stored data and metadata against the destination head, rejects every conflict before mutation, then creates a fresh committed revision and selects it as head. Preserve source payloads and default platform inheritance. Correct the relevant existing asynchronous batch URL and optional-query discrepancies; add no workflow methods to clients.

## Technical Context

**Language/Version**: Python 3.13+; verification matrix follows existing Python 3.13 and 3.14 CI.

**Primary Dependencies**: Existing HTTPX, Pydantic/Pydantic Settings, PyYAML, and python-benedict. Use standard-library JSON, pathlib, base64, hashlib, datetime, and asyncio; no new dependency or lockfile change planned.

**Storage**: UTF-8 input files and an in-memory staged dictionary; configuration/revision/artifact storage remains in the existing platform.

**Testing**: pytest, pytest-asyncio, pytest-mock, HTTPX MockTransport, existing serialization and settings-source tests, and Ruff 0.16.9.

**Target Platform**: Existing SDK-supported Python environments with access to the rapyuta.io v2 service.

**Project Type**: Typed Python library with synchronous and asynchronous public interfaces.

**Performance Goals**: Exactly one create call per successful workflow; one batch key write for a nonempty dictionary, zero for an empty one, and no per-key writes. Transformation/compatibility work is linear in document size and key count, apart from deterministic conflict reporting. No latency or maximum-document-size guarantee is invented.

**Constraints**: Preserve one-to-one clients and typed payload contracts; all input/merge conflicts fail before creation; maintain independent source/destination scopes; no CLI state, prompts, editor, mutation retries, rollback, partial merge, or extra batch chunks. Async platform I/O is awaited; local Import preparation uses `asyncio.to_thread`. Original exceptions and cancellation survive with recovery annotations. One batch must fit the platform's existing request limits; failures are propagated.

**Scale/Scope**: Two workflows, two revision contexts, one refspec parser, three options models, private shared helpers, and focused client corrections. Large-document streaming, concurrent-writer transactions, unrelated pagination fixes, and broader CLI features are excluded.

## Constitution Check

Design gates were evaluated before research and again after Phase 1. No proposed exception or amendment is needed. Existing behavior does not excuse new noncompliance.

| Principle/gate | Initial assessment | Post-design assessment |
| --- | --- | --- |
| I. Modern Python SDK | Python compatibility and typed helpers required | Pass: typed public contracts, documented failures, current package identity, 3.13+ syntax |
| II. One-to-One API Clients | Existing async batch URL/query discrepancies identified | Pass for the design: narrow corrections are explicitly required; all six client methods remain single operations; actual code corrections remain implementation work |
| III. Pydantic Contracts | Existing payload/response models available; mutated instances can bypass validation | Pass: final plain-field snapshot validated as `ConfigValues`; typed commit/head payloads; aliases and field presence preserved |
| IV. Separate Higher-Level Modules | No existing Revision helper | Pass: orchestration/context helpers in `configtree/`, outside both client modules |
| V. Ruff Compliance | Existing strict configuration applies | Pass for the design: options objects and small composed helpers avoid oversized signatures/functions; Ruff gates remain mandatory during implementation |
| Workflow/review governance | Affected operations, models, and helpers must be identified | Pass: operation table, source layout, contracts, and verification matrix below provide that inventory |

The low-level corrections are prerequisites to async workflow verification, not exceptions to principle II. They are justified by local primary platform sources in [research.md](research.md).

## Project Structure

### Documentation (this feature)

```text
specs/001-configtree-import-merge/
├── spec.md
├── checklists/requirements.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── sdk-interface.md
    └── revision-lifecycle.md
```

`tasks.md` is intentionally reserved for the subsequent `$speckit-tasks` phase.

### Source Code (repository root)

```text
rapyuta_io_sdk_v2/
├── client.py                         # Preserve current synchronous operations
├── async_client.py                   # Correct batch URL and query omission
├── models/
│   ├── configtree.py                 # Reuse existing wire contracts
│   ├── configtree_operations.py      # RevisionOptions, ImportOptions, MergeOptions
│   └── __init__.py                   # Export options models
├── configtree/
│   ├── __init__.py                   # Public workflow/context/parser exports
│   ├── _documents.py                # Safe parsing, wrapper split, path flattening
│   ├── _values.py                   # Encoding, strict snapshots, compatible union
│   ├── _scope.py                    # Immutable per-call scope snapshots
│   ├── _refs.py                     # Refspec tuple and scoped milestone resolution
│   ├── _lifecycle.py                # Shared local state, commit preparation, recovery
│   ├── revision.py                  # Revision and AsyncRevision
│   ├── workflows.py                 # Four sync/async workflow functions
│   └── exceptions.py                # Domain input/reference/conflict/envelope errors
└── pydantic_source/source.py         # Reuse wrapper splitting without parser changes

tests/
├── test_configtree_helpers.py        # Shared pure transformations/options validation
├── test_model_contracts.py           # Existing and extended wire parity coverage
├── utils/configtree_operations.py    # Shared stateful MockTransport support
├── sync_tests/
│   ├── test_configtree.py            # Existing low-level contracts, scope/query parity
│   ├── test_configtree_operations.py # Import, Merge, mutable contexts, failures
│   └── test_pydantic_source.py       # Preserve settings-source behavior
└── async_tests/
    ├── test_configtree_async.py      # Corrected low-level request contracts
    └── test_configtree_operations_async.py # Async parity and cancellation

README.md                            # Public workflow usage and limits
```

**Structure Decision**: Use the existing single SDK package and test layout. Shared pure helpers handle local transformations/state; separate explicit sync/async methods perform transport work. Options models belong in model modules. Public exports live in `rapyuta_io_sdk_v2.configtree`; do not require top-level convenience re-exports or unrelated source refactoring.

## Phase 0: Research Decisions

Research is complete in [research.md](research.md). Decisions cover rio wrapper/traversal semantics, duplicate-aware safe document parsing, typed dictionary snapshots, scope routing, canonical batch URL, optional query parity, numeric milestone pagination, empty-map wire semantics, committed-parent inheritance, commit defaults, and failure/cancellation behavior.

Planning setup used the available `python` interpreter because `.venv/bin/python` is absent. The standard-library setup script resolved the correct feature directory and copied the plan template. Its JSON `BRANCH` value is the feature basename (`001-configtree-import-merge`), because the script does not inspect Git by default; the actual Git branch remains `feat/configtrees` and is used throughout these artifacts.

## Phase 1: Design

### Operations and model composition

| Existing operation in both modes | Workflow use | Models and sequencing |
| --- | --- | --- |
| `get_configtree` | Destination existence/base and source content | `ConfigTree`; Merge requests key-value data and a resolved revision selector |
| `list_revisions` | Milestone uniqueness across pages | `ConfigTreeRevisionList`, `ListMeta`; numeric continuation, exact label verification |
| `create_revision` | Context entry, once | `ConfigTreeRevision`; optional pinned parent for Merge, no keys in initialization payload |
| `put_keys_in_revision` | Context exit, one nonempty batch | `ConfigValues` containing validated `ConfigValue` entries; check `APIResponse` failure fields |
| `commit_revision` | After successful storage when requested | `ConfigTreeRevision` plus `ConfigTreeRevisionMetadata`; nonempty author/message and retained labels |
| `set_configtree_revision` | After context success when requested | `ConfigTree(metadata=BaseMetadata(name=...), head=ConfigTreeRevision(metadata=ConfigTreeRevisionMetadata(guid=...)))` |

Preserve existing wire field aliases, `exclude_unset=True`, JSON mode, and response validation. Correct only the two relevant async transport discrepancies. Do not add keys to the revision initialization body or bypass clients with raw HTTP calls.

### Workflow sequence

1. Import: validate files/options/scope and prepare the full typed key map; verify the target exists; create one revision through the context; update its live dictionary; finalize one batch and optional commit; optionally select head; return revision ID.
2. Merge: parse and resolve source; read source and destination selected revisions in their separate scopes; reject omitted or null whole key maps while accepting explicit empty maps; reject any selected source key with absent or inconsistent byte-based content length before creation; compute compatible union or reject conflicts; prepare commit metadata; create with the checked destination head as parent; batch and commit; select head; return ID.
3. Context: construct locally; initialize on entry; allow live typed dictionary edits; on normal exit snapshot/validate, batch if nonempty, and commit if configured; body exceptions/cancellation skip finalization. The async context snapshots before awaiting the batch and never shields cancellation.
4. Publication errors: stop, annotate original failure with known revision ID/stage, and propagate. A nonempty batch requires `success=true` and no nonempty error; missing, null, or false success stops publication. Remotely completed operations cannot be rolled back reliably.

### Validation and compatibility

Metadata recognition is structural and precedes schema validation. Opaque extracted metadata must satisfy `dict[str, str]`; its field names may contain slashes. Lists remain content, including wrapper-shaped objects. Wrapped mapping values flatten normally without metadata inheritance. Keep the settings loader's parsing/flattening unchanged when sharing the splitting implementation.

The public dictionary stores `ConfigValue` entries. Rebuild final values from independent plain mappings, preserving field presence; validate key names and key-value storage prerequisites, including actual data, key-value content type, checksum, and content length equal to decoded byte count. Use the staging helper for logical value replacement; direct payload replacements must remain consistent with their encoded data. Merge validates every selected source key's length before creating a destination revision, including shared keys; invalid legacy lengths fail with the key identified and are not recalculated. Do not globally tighten the low-level models.

Parent inheritance is platform behavior: initialization copies a committed parent (normally the current head). A staged removal therefore removes a pending write, not an inherited key. Merge pins the checked parent; head selection still lacks compare-and-swap. A data-included Merge response must contain a non-null `keys` map, including `{}` for an empty revision.

### Verification matrix

| Area | Required evidence | Spec coverage |
| --- | --- | --- |
| Import inputs | JSON/YAML/YML mix; suffix/stem rules; nested maps; lists; Unicode and non-UTF-8 paths; YAML merge overrides and authored duplicate rejection; null/false/zero; malformed inputs fail before creation | FR-002–FR-006, FR-014, SC-001–SC-002 |
| Metadata | All table examples; nested wrappers; empty metadata; invalid metadata; list/root boundaries; wrapped maps; no leaked metadata paths | FR-020–FR-022, SC-008 |
| Refspec/scopes | Six forms; invalid grammar; both directions across scopes; unknown references; late-page duplicates; advancing and malformed tokens | FR-008–FR-011, SC-003 |
| Merge | Exact data/metadata equality; all conflict names; no mutation on conflict, invalid source length, or missing key map; union; explicit empty maps; same-tree merge; no source changes | FR-011–FR-015, SC-004–SC-005 |
| Mutable contexts | Dictionary identity/isolation; add/replace/remove/clear inside the context body; invalid mutated model instances; no promised behavior for retained-reference edits after body exit | FR-017, FR-023–FR-025, SC-009–SC-010 |
| Failure lifecycle | Zero/one batch counts; order; body/storage/commit/head failures; missing/null/false batch success; original error type plus ID/stage; cancellation at each await | FR-001, FR-007, FR-016–FR-018, SC-006 |
| Low-level parity | Canonical URL; optional query omission; source/destination headers; aliases and omitted fields; typed responses | Constitution II–III |
| Regression/quality | Settings loader tests, complete SDK test suite, Ruff 0.16.9 lint/format on Python 3.13/3.14 | Constitution I, V; SC-007 usage validation |

Focused tests precede the complete regression suite because shared splitting and low-level transport methods are affected. [quickstart.md](quickstart.md) supplies exact commands and manual validation scenarios. No implementation tests have been run as part of planning; only artifact consistency and existing Ruff gates are checked now.

### Completion and next phase

Generated [data-model.md](data-model.md), [SDK interface contract](contracts/sdk-interface.md), [revision lifecycle contract](contracts/revision-lifecycle.md), and [quickstart.md](quickstart.md). Post-design constitution gates pass with no exceptions. Extension hooks are absent. The next phase is `$speckit-tasks`; implementation and functional verification remain pending.
