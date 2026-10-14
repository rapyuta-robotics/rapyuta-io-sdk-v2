# Implementation Plan: Device Management and Command Responses

**Branch**: `feat/device` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-device-management/spec.md`

## Summary

Add 20 individual Device Management operations to the existing `Client` and `AsyncClient`, using identical public names, typed arguments, defaults, and response models. Reuse the core service host, client transports, configuration headers, and SDK HTTP exception categories. Cover lifecycle/onboarding, selection, labels, configuration variables, Parameter application, command submission/retrieval, migration, and VPN-only control. Do not expose topic operations, agent upgrade, or general daemon changes.

Add separate sync/async helpers for command submission and complete response collection. Helpers submit once, preserve empty and partial per-device output, recognize only the exact backend pending envelope, and expose typed failure/cancellation context. The user clarified that sync deadlines stop new polling and cap network-operation timeouts, while an already-started request may finish later; async uses a cancellable overall deadline. No replacement transport, background thread, retry, or remote cancellation is needed.

Design and evidence are in [research.md](research.md), [data-model.md](data-model.md), [contracts/sdk.md](contracts/sdk.md), and [quickstart.md](quickstart.md). Implementation progress is tracked in [tasks.md](tasks.md); executed acceptance evidence is recorded in [quickstart.md](quickstart.md).

## Technical Context

**Language/Version**: Python 3.13+, as declared in `pyproject.toml`.

**Primary Dependencies**: Existing HTTPX >=0.27.2, Pydantic v2 through pydantic-settings >=2.7.1, and stdlib time/asyncio/enum/urllib.parse. No new runtime dependency. Keep the existing reference dependency group pinning SDK v1 revision `739a6fe44600ff0964fa56b04878ddb21e76b5be`.

**Storage**: No local persistence, database, or migration. Existing remote Device Manager, Parameter application, and VPN-related platform services own state. Helpers retain in-memory job identity and immutable result snapshots only.

**Testing**: Existing pytest, pytest-asyncio, pytest-mock, HTTPX MockTransport, model-contract discovery, and network-isolated pinned reference SDK replay. Deterministic clock/transport tests establish polling/deadline behavior; a focused real-event-loop responsiveness/cancellation test establishes async progress. Ruff 0.16.9 remains the required lint/format gate.

**Target Platform**: Supported Python desktop/server platforms with existing HTTPX transports. No platform-specific socket interruption or thread-based deadline mechanism.

**Project Type**: Typed Python SDK library, retaining rapyuta-io-sdk-v2 / rapyuta_io_sdk_v2 identity.

**Performance Goals**: Collect all responses for at least three explicit devices through one helper invocation with exactly one submission; default wait budget 300 seconds and poll interval 10 seconds. No requests/waits start after the deadline. Each command call caps network timeout components to its remaining budget; a sync in-flight request may overrun, and its late response cannot yield success. Async deadline tolerance is one second in controlled checks; a 50 ms heartbeat has no gap over 250 ms.

**Constraints**: One platform operation per client method; actual legacy envelopes and payloads, including token registration responses and empty mutation acknowledgments; exact HTTP400 pending detection on result lookup only; explicit target identity and no hidden fleet expansion. Preserve supplied transport/client ownership. Do not mutate command inputs or default timeouts. Python/ROS historical defaults that the current registration handler ignores must not be advertised as persistence guarantees. Public models are strict/typed and responses preserve observed fields.

**Scale/Scope**: 20 operations implemented in both clients, shared Device and workflow models, two helpers, additive VPN response-model fields, nested error extraction, and focused compatibility/regression verification. No new CLI, streaming output, general daemon mutation, topics, agent upgrade, deprecated metrics, hardware provisioning, retries/resume, or installation workflow.

## Constitution Check

Reviewed before Phase 0 research and again after Phase 1 design. All gates pass; no amendment or exception is required.

| Principle / constraint | Pre-research gate | Post-design evidence |
| --- | --- | --- |
| I. Modern Python SDK | Pass: Python 3.13+, typed public interfaces | Twenty signatures, named models, documented outputs/errors, and runnable validation guide |
| II. One-to-one API clients | Pass: individual operations only | Contract matrix maps every method to one HTTP operation; helper polling/aggregation is outside clients; every new async call awaits the supplied async transport |
| III. Pydantic payload contracts | Pass: preserve typed requests/results | Named bodies/query models and actual success/pending/token envelopes; JSON mutations return validated named acknowledgments; scalar route identifiers remain scalar |
| IV. Separate higher-level modules | Pass: workflow helpers in helpers/ | Sync/async helper modules compose public command methods; shared progress/deadline logic is private and pure |
| V. Ruff compliance | Pass: retain version and strict rules | Small shared parsing/routing/validation functions, options models and typed kwargs avoid broad signatures; implementation runs pinned lint/format checks |
| Package and wire identity | Pass: preserve current namespace/configuration | Reuse core_api_host, explicit aliases, omitted-field handling, SDK headers/errors, and existing clients; no v1 mutable resource object or second HTTP stack |
| Verification | Pass: source-backed fixtures and parity | All operations, command edge cases, VPN restriction, deadlines/cancellation, signature/model parity, and actual pinned reference replay with zero skipped required cases |
| Existing behavior | Pass: additive scoped changes | Existing daemon read remains; optional SSH certificate and encoded pull-secret response fields preserve returned data; top-level error extraction, Parameter, file-upload, and existing exports remain compatible |

Existing synchronous identity/authentication methods on `AsyncClient` are pre-existing constitution noncompliance; they do not establish a precedent for new Device methods. This feature does not refactor unrelated authentication. Existing generic Daemon model defaults remain unchanged; a typed response field addition does not authorize a public daemon-write operation.

## Project Structure

### Documentation (this feature)

```text
specs/002-device-management/
├── spec.md
├── checklists/requirements.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
└── contracts/
    └── sdk.md
```

`tasks.md` records the completed implementation phases and their acceptance gates. The Spec Kit active directory is persisted in `.specify/feature.json`; its synthesized feature identifier is `002-device-management`, independently of the actual Git branch `feat/device`.

### Source Code (repository root)

Implemented layout:

```text
rapyuta_io_sdk_v2/
├── client.py                       # 20 synchronous methods
├── async_client.py                 # 20 matching awaitable methods
├── _device_api.py                  # routing, query/wire parsing, timeout caps
├── _client_options.py              # DeviceCommandCallOptions
├── utils.py                        # compatible nested HTTP error extraction
├── exceptions.py                   # Device contract/workflow exceptions
├── __init__.py                     # model exports using current convention
├── models/
│   ├── __init__.py                  # new named Device model exports
│   ├── device.py                    # API models and envelope types
│   ├── device_command.py            # command, waiting, immutable outcome models
│   └── daemons.py                   # SSHCertConfig and pull_secret.auth fields
└── helpers/
    ├── __init__.py                  # command helper exports
    ├── device.py                    # execute_device_command
    ├── async_device.py              # execute_device_command_async
    └── _device_command.py           # pure budget/progress/snapshot functions

tests/
├── data/device_data.py              # pinned source/test-derived fixtures
├── test_device_api.py               # foundational routing/envelope contracts
├── test_device_models.py            # actual envelope/request validation
├── test_device_command_models.py    # variants, defaults, snapshots
├── test_device_examples.py          # isolated runnable-example validation
├── test_device_errors.py            # paired refusals and transport ownership
├── device_contract_support.py      # shared golden request assertions
├── test_model_contracts.py           # discovery/aliases/typed request regressions
├── sync_tests/test_device.py         # all routes, contexts, errors, one request
├── sync_tests/test_utils.py          # top-level/nested error regressions
├── async_tests/test_device_async.py  # corresponding contracts and awaitability
├── helpers/test_device_command.py
├── helpers/test_device_command_async.py
└── reference/
    ├── conftest.py                  # scoped replay guard and existing skip gate
    └── test_device_compatibility.py # pinned SDK actual serialization replay

examples/devices/
├── _configuration.py                # explicit example environment loading
├── manage.py                        # discovery, registration, VPN, metadata
├── manage_async.py
├── command.py                       # single/multi, immediate/deferred, failures
└── command_async.py                 # matching flows and cancellation
README.md                           # public entry points and example links
```

**Structure Decision**: Extend the existing library layout, sharing pure wire/model/state logic across clients and helpers. Do not add managers, transport wrappers, a new service package, or a second client ownership lifecycle. Only `_device_api.py` performs common request preparation/response interpretation; actual I/O remains in the existing client modules. Helper modules never construct requests directly or access private transport internals.

## Phase 0 — Research decisions

All initial unknowns are resolved in [research.md](research.md): canonical core routing, actual registration and mutation envelopes, lifecycle/selection/config contracts, VPN response schema, exact pending command response, sync timeout limitations, immutable helper state, and fixture-based compatibility. User timeout clarification updates FR-008/SC-005 rather than making an unsupported strict deadline claim.

## Phase 1 — Design and validation

1. **API and models:** Implement the 20-operation matrix from the SDK contract and entities from the data model. Resolve routing dynamically and safely encode scalar segments. API models preserve service payloads rather than reuse v2 Device schemas. Validate copied request models before making one request. Both modes return the same named models.
2. **Error adaptation:** Add nested message extraction to shared HTTP handling without changing status mappings. Device parsing rejects false-success error envelopes and malformed bodies. Exact pending recognition is limited to command result lookup. Keep known pending results distinct from failed submissions and offline/permission errors.
3. **VPN:** Translate only typed VPN state/config through the existing internal daemon route. Parse the actual nested Daemon response, preserving kind, SSH certificate configuration, and the pull-secret auth field. Add these missing typed response fields without changing existing defaults. Do not add public topic/upgrade/generic-daemon methods.
4. **Commands:** Use validated mode-aware job/output variants. Direct lookup repeats device_id query keys and returns one result/pending model. Public command calls accept a typed optional request_timeout cap while retaining header overrides and supplied transport settings.
5. **Helpers:** Compose the public methods, submit once, collect outputs for remaining targets, preserve ordered immutable snapshots, and use monotonic deadline accounting. Default immediate execution stays explicit; deferred mode uses the returned JID. Async uses awaitable I/O/sleeps and overall cancellation. Exceptions expose required stage/message, optional jid defaulting to None, and required requested_devices/missing_devices tuples. The identity fields must match the associated partial_result snapshot exactly; outputs remain in partial_result.responses and causes are chained when available. Helpers never mutate or close caller-owned clients.
6. **Documentation and verification:** Provide runnable examples with discovery/onboarding, VPN enable/disable, direct commands, helpers, empty output, partial timeout and cancellation. Verify every FR and success criterion through the matrix below. Record actual executed results and preserve reviewer-owned checklist markers.

## Verification matrix

| Requirement / outcome | Required evidence |
| --- | --- |
| FR-001–003, SC-001–002 | All 20 exact verbs/routes/bodies/envelopes, typed inputs/results, contexts, default/overridden host, route safety, mutation acknowledgments, sync/async signatures/defaults/errors; SC-001 preserves transmitted request values and returned identities without asserting persistence of ignored fields |
| FR-004–005 | Exact text/options, immediate/deferred/background variants, opaque JID, repeated lookup keys, one request per client call, terminal versus exact pending responses |
| FR-006–007, FR-012, SC-003 | One submission for single/multi targets; three staggered responses; empty output; immutable target-order aggregation; duplicate/conflicting/unexpected outputs; incomplete immediate/job acknowledgments |
| FR-008, SC-005 | Remaining-budget caps for all timeout phases including unlimited components; no default timeout mutation; elapsed request/sleep accounting; zero new work after deadline; late sync result is timeout, not success |
| FR-009–011, SC-004 | Preflight invalid inputs/background; submission/retrieval/contract failures and chained causes; unknown acceptance; partial timeout/cancellation; no automatic replay or remote cancellation |
| FR-010, SC-005 | True awaited network/sleep, event-loop heartbeat, cancellation during submit/lookup/sleep, deadline versus external cancellation distinction, supplied clients remain open |
| FR-013 | Label map/record IDs; config online/reserved-key failures; exact Parameter outcomes even when unknown devices omitted; VPN true/false/route default/explicit route and restricted keys; migration refusals and source context |
| FR-014, SC-006 | Execute documented examples against isolated fixtures; inputs/outputs follow contract; live guide remains supplemental and does not print real onboarding tokens |
| FR-015 | Pinned v1 actual public serialization replay where available plus source-derived goldens for every operation, no live requests or skipped required compatibility cases, no excluded public APIs |
| Existing behavior / quality | Shared error handling top-level+nested cases; Daemon read/SSH field; file uploads, ConfigTree, Parameter operations/helpers, typed model/export discovery; Ruff check/format and full existing test suite |

Implementation acceptance requires the concrete commands in [quickstart.md](quickstart.md). Executed implementation results and environment details are in the validation guide.

## Implementation reconciliation

All 68 implementation tasks, including T065–T068 from convergence, are complete. All 20 contract operations are implemented in both clients, with two separate command helpers. The implementation retains one-operation methods, named Pydantic payloads, Python 3.13 compatibility, supplied transport/context ownership and the existing package/runtime dependency set. Public deprecated/internal operations remain excluded.

Final acceptance passed 1,002 targeted checks and the complete 1,776-test suite, with no skipped cases. Ruff 0.16.9 lint and formatting passed unchanged rules. The validation guide maps every FR-001–015 and SC-001–006 to executed evidence and records the sandbox limitation affecting pre-existing async Parameter tests. There is no remaining required work; reviewer-owned quality checklist markers were not changed.


Convergence corrections preserve valid requested output from malformed batches independently of JSON key ordering and retain validated job identity on actual-client execution-mode mismatch failures. Recovery uses requested targets and the named output contract to keep a requested jid device's string output from becoming a job identifier on deferred-mode failures, while retaining separately validated identity from malformed job acknowledgments. VPN acceptance includes exact enable/disable/default/advertisement request assertions in both clients and the examples. Device health reports use the daemon_status field with the actual daemons_status wire alias. These corrections retain terminal failures, cause chaining, one-operation clients, caller ownership and the clarified deadline semantics.
