# Implementation Plan: Parameter Uploads

**Branch**: `chore/bootstrap-spec-kit` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-parameter-uploads/spec.md`

## Summary

Add v1 Parameter support to the existing synchronous and asynchronous clients, then expose separate helpers for submitting local directories as Parameter trees. Implement nine individual methods covering the seven specified operation categories, named Pydantic request/response contracts, and environment-aware core service configuration. Helpers preserve folder and legacy hierarchies, select trees, optionally recreate them, classify inline versus binary content, transfer blobs, verify completion, and report partial outcomes.

Reuse HTTPX, Pydantic, and PyYAML. Use isolated storage transports and sequential bounded transfers rather than porting the legacy thread-pool implementation. Source-backed decisions, including response envelopes, versions, deduplication, and Azure transfer protocol, are recorded in [research.md](research.md). The exact public interface and wire contracts are in [contracts/sdk.md](contracts/sdk.md) and [contracts/storage.md](contracts/storage.md).

## Technical Context

**Language/Version**: Python 3.13+, preserving the package's declared compatibility.

**Primary Dependencies**: Existing `httpx>=0.27.2`, Pydantic v2 provided by `pydantic-settings>=2.7.1`, and `pyyaml>=6.0.2`; stdlib pathlib, mimetypes, hashlib, Base64, XML, and asyncio. No new runtime dependency is planned. A test-only `reference` dependency group pins `rapyuta-io` to SDK revision `739a6fe44600ff0964fa56b04878ddb21e76b5be` for the mandatory consumer compatibility gate.

**Storage**: Local source filesystem, existing project-scoped v1 Parameter service, and signed Azure Block Blob uploads. No local persistence or database migration.

**Testing**: Existing pytest, pytest-mock, pytest-asyncio, model-contract checks, and HTTPX MockTransport. Acceptance requires an isolated round-trip through the pinned SDK v1 public downloader with no skipped cases or live requests. Supplemental live interoperability uses a disposable project and configured CLI/SDK v1 and is reported separately.

**Target Platform**: Python-supported desktop/server platforms with HTTP access to the configured services. Portable traversal uses pathlib/lstat; inode/device checks are strengthened where available without promising atomic snapshots.

**Project Type**: Typed Python SDK library.

**Performance Goals**: One helper invocation submits the SC-001 fixture of two trees, 100 mixed files, and five levels without per-file orchestration. At most one file/block payload is processed at a time; storage blocks are 4 MiB. Async disk work is offloaded and network work remains awaitable so unrelated tasks progress.

**Constraints**: Preserve v1 wire keys and version semantics; source limit is 128 KiB for inline candidates with the reference's serialization/metadata estimate. Blob file support is up to 209715200000 bytes (50000 blocks of 4 MiB). Files above that bound fail preflight. No automatic retry/resume/rollback; no concurrent-writer atomicity; no platform credentials on storage requests. Existing Ruff 0.16.9 rules remain unchanged.

**Scale/Scope**: Nine client operations, shared named models, two helper entry points, core endpoint configuration, documentation/examples, and targeted behavioral/regression verification. Device apply, download/diff helpers, new CLI commands, and ConfigTree migration are excluded.

## Constitution Check

Gates were reviewed before research and again after Phase 1 design. Both reviews pass; no exception or constitution amendment is needed.

| Principle / constraint | Pre-research gate | Post-design evidence |
| --- | --- | --- |
| I. Modern Python SDK | Pass: retain Python 3.13+ and typed public contracts | All proposed signatures and models are named; inputs, results, ownership, failures, and validation are documented |
| II. One-to-one API clients | Pass: individual operations only | Nine methods map to nine single HTTP operations; async counterparts await their transport; workflow and dedup verification stay outside clients |
| III. Pydantic contracts | Pass: no untyped public payloads | Node write/delete, header/query inputs, recursive node, tree/blob lists, and acknowledgments have named models; no-payload operations are explicitly identified |
| IV. Separate higher-level modules | Pass: orchestration in helpers | `helpers/parameter.py`, `helpers/async_parameter.py`, and private source/upload/storage modules compose public client methods |
| V. Ruff compliance | Pass: keep strict settings and required version | Small functions, options models rather than wide signatures, and focused modules; implementation must run pinned lint/format gates |
| Package and wire compatibility | Pass: preserve existing package and clients | Explicit aliases, `exclude_unset=True`, no v2 resource schema reuse, append config field, retain existing host/error conventions |
| Verification and review | Pass: verify changed contracts | Source-backed response/serialization cases, sync/async parity, typed cancellation outcomes, transfer protocol tests, ConfigTree regressions, required actual reference downloader round-trip; live checks supplemental |

Existing `AsyncClient` synchronous identity/authentication methods do not satisfy the async principle; this is pre-existing noncompliance and does not establish a pattern for the new Parameter methods. New methods use only awaitable HTTPX network I/O. No unrelated authentication refactor is included.

## Project Structure

### Documentation (this feature)

```text
specs/001-parameter-uploads/
├── spec.md
├── checklists/requirements.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── sdk.md
    └── storage.md
```

`tasks.md` is the subsequent `$speckit-tasks` artifact and is not created by planning.

### Source Code (repository root)

```text
rapyuta_io_sdk_v2/
├── client.py                      # nine synchronous operations
├── async_client.py                # nine awaitable operations
├── config.py                      # appended core_api_host and resolution
├── utils.py                       # robust HTTP error-body extraction, if needed
├── _parameter_api.py              # pure routing/header/query/response utilities
├── exceptions.py                  # ParameterUploadError
├── __init__.py                    # public model exports
├── models/
│   ├── __init__.py                 # Parameter model exports
│   └── parameter.py               # API and helper models
└── helpers/
    ├── __init__.py                 # two helper entry-point exports
    ├── parameter.py               # upload_parameters
    ├── async_parameter.py         # upload_parameters_async
    ├── _parameter_source.py       # preflight, traversal, classification, hashing
    ├── _parameter_upload.py       # progress, failures, dedup matching
    └── _parameter_storage.py      # sync/async signed-URL transfer adapters

tests/
├── data/parameter_data.py          # shared wire/source/state fixture factories
├── test_model_contracts.py         # existing discovery/alias regressions
├── test_parameter_models.py       # actual v1 schema, input validation
├── test_parameter_storage.py      # MockTransport bytes/protocol/ownership
├── helpers/
│   ├── test_parameter_upload.py
│   └── test_parameter_upload_async.py
├── sync_tests/
│   ├── test_config.py             # core resolution + existing host behavior
│   └── test_parameter.py          # synchronous operation contracts
├── async_tests/
│   └── test_parameter_async.py    # corresponding operation contracts
└── reference/
    ├── conftest.py                # reference provenance/execution/skip gate
    └── test_parameter_compatibility.py  # actual SDK v1 download round-trip

examples/parameters/
├── upload.py
└── upload_async.py
README.md                          # usage and links to examples
pyproject.toml                     # test-only pinned reference group
uv.lock                            # reproducible reference dependency resolution
```

**Structure Decision**: Extend the existing library layout. Shared private Parameter utilities remain transport preparation/parsing only, with no network orchestration. Separate helpers reuse public operations and small shared local/protocol functions. Keep new public payload classes together in the SDK model module; avoid copying legacy classes or introducing a general transport framework.

## Phase 0: Research results

All unknowns are resolved in [research.md](research.md):

1. Server routes and operation boundaries, including tree-only GET and child DELETE bodies.
2. Required v1 envelopes, exact node/blob ID types, aliases, and optimistic versions.
3. Core API production/staging routing and explicit local configuration.
4. Reference file classification, default folder mode, opt-in legacy mode, source checks, and deterministic traversal.
5. Dedup verification using the matching ID/checksum/status, instead of blind error suppression.
6. Existing-dependency HTTPX storage protocol and bounded block transfers.
7. Async disk/network separation, cancellation, resource ownership, and typed partial results.
8. Repository error conventions, compatibility fixtures, and meaningful verification.

Research did not upload to a live project. Source revision evidence and primary protocol documentation are included so implementation can verify assumptions against deployed responses.

## Phase 1: Design

### Individual clients and model boundaries

The nine methods in [contracts/sdk.md](contracts/sdk.md) are `list_parameter_trees`, `create_parameter_tree`, `get_parameter_tree`, `put_parameter_node`, `delete_parameter_tree`, `delete_parameter_node`, `list_parameter_blobs`, `prepare_parameter_upload`, and `commit_parameter_upload`. Each uses one HTTP call and the exact named model described in [data-model.md](data-model.md).

Read the configured core endpoint at call time. Use existing header/context options, aliased serialization, and a narrowly scoped v1 response checker. Preserve existing exception taxonomy. If the shared error handler needs defensive support for JSON error bodies that are not objects, extract their display text without incidental attribute errors; verify existing mappings remain unchanged rather than duplicate the mapping table. No node traversal, source-file reading, blob transfer, status follow-up, or implicit version refresh occurs in clients.

### Helper workflow

Preflight selected source metadata and options before mutations. For each selected tree, optionally delete, create the root, create parent-first directories, and process each eligible file once. Default folder mode covers all nested eligible files and empty folders. Legacy mode deliberately skips attribute-level files. Preserve failures when a root already exists without recreation; do not silently merge.

Structured candidates at or below the 131072-byte raw threshold preserve original UTF-8 text and validate before the stored-size decision; larger structured files and other extensions bypass parsing. An eligible blob above 209715200000 bytes fails preflight before remote mutations. Blobs use a prehash and second transfer hash, isolated storage requests, and explicit platform completion. Dedup and ambiguous duplicate completion require a matching uploaded reference. Ordinary failure and cancellation both expose typed failure context and an immutable snapshot of known progress. Cancellation uses `ParameterUploadCancelled`, a `CancelledError` subclass exposing `.failure: ParameterUploadFailure` and `.partial_result: ParameterUploadResult`, releases resources, and never confirms unfinished content.

### Implementation ordering

1. Add core configuration and validated Parameter models, then shared request/response utilities.
2. Add all synchronous/asynchronous single operations with source-backed serialization and error checks.
3. Add shared local preflight/classification/progress and private sync/async storage adapters.
4. Add the two helpers and verify selection, recreation, hierarchy, dedup, partial failure, and async behavior.
5. Publish examples/exports, implement the required `tests/reference/test_parameter_compatibility.py` consumer round-trip, run it with the pinned reference group and existing regression/quality checks, then record any supplemental live reference-tool validation separately.

This ordering informs task generation; it is not an executable task checklist or an implementation completed by this command.

## Validation Strategy

| Requirement / outcome | Required evidence |
| --- | --- |
| FR-001–FR-003; SC-002 | Nine method mappings on both clients, request aliases, query/header projection, no-body requests, version-aware child deletion, strict response validation, host/context overrides and failures |
| FR-004–FR-007; SC-001 | Two-tree 100-file five-level fixture; exact selection, parent-first folders, empty directories, legacy alternating types and skipped files |
| FR-008–FR-010; SC-004 | Original inline text including line endings; raw-route bypass versus candidate validation before serialized-size decision; 128 KiB boundaries; binary checksums; empty and multi-block storage; verified dedup and malformed authorization |
| FR-011–FR-013; SC-003 | No deletion by default; selected-only recreation; deletion failure; no matches/no-op; exact maximum-file-size boundary and zero mutations for an oversized eligible blob; symlink/special/hidden entry handling and literal path restrictions |
| FR-014–FR-015; SC-005 | Failure injection at each stage; exact partial report on ordinary failure and cancellation, including identities/skips/known deletions; no completion after transfer/verification failure; asynchronous heartbeat, bounded payload reads and ownership |
| FR-016; SC-006 | Runnable sync/async examples for filter, recreation, legacy mode, and errors using only documented contracts |
| FR-017; SC-004 | Existing ConfigTree/configuration/model regressions and mandatory isolated round-trip through the actual SDK v1 public downloader for both helpers and hierarchy modes; zero skipped reference cases. Live CLI/SDK comparison is supplemental |
| Constitution V | `uvx ruff==0.16.9 check .` and `uvx ruff==0.16.9 format --check .` |

Use the concrete commands and expected outcomes in [quickstart.md](quickstart.md). Planned tests are requirements for implementation; planning only validates the consistency and completeness of these documents.

## Planning Completion

Phase 0 research and Phase 1 models/contracts/validation guide are complete. Post-design constitution gates pass. No extension hooks are registered (`.specify/extensions.yml` is absent). Setup used system `python3` for the stdlib-only setup script because this checkout has no `.venv/bin/python`; no runtime environment was installed for document generation. The script's initial branch output was a feature-directory fallback; rerunning with `SPECIFY_FEATURE=chore/bootstrap-spec-kit` aligned it with the actual Git branch without switching branches.
