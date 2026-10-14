---

description: "Dependency-ordered implementation tasks for Apply template rendering parity"
---

# Tasks: Apply Template Rendering Parity

**Input**: Design documents from `specs/002-apply-render-parity/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [SDK contract](contracts/sdk-rendering.md), [fixture contract](contracts/fixture-provenance.md)

**Tests**: Required by the feature specification. Capture CLI reference results before asserting SDK output. Write each story's tests before its implementation and confirm the expected failures.

**Organization**: Tasks are grouped by user story. `[P]` means the listed work uses different files and has no dependency on another incomplete task at the same point.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Make the required Ansible filters installable and the local test environment writable.

- [X] T001 Add `ansible-core>=2.21,<2.22` as a normal runtime dependency in `pyproject.toml`, resolve it into `uv.lock`, and verify the resolved version supports Python 3.13.
- [X] T002 [P] Configure `tests/apply/conftest.py` to set a writable `ANSIBLE_LOCAL_TEMP` before any lazy Ansible filter import, with test cleanup that does not alter the caller's permanent environment.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared, source-aware rendering and a reproducible CLI fixture capture path before either direct-filter story starts.

- [X] T003 Create `rapyuta_io_sdk_v2/apply/_filters.py` with an environment factory that retains `ImmutableSandboxedEnvironment`, `StrictUndefined`, and `autoescape=False`, and provides a registration point for rio and Ansible filters.
- [X] T004 Route per-file environment creation and filter initialization failures through `rapyuta_io_sdk_v2/apply/_loader.py`, preserving `ApplierValidationError(category="template")` and the input file's `SourceLocation` before resource operations.
- [X] T005 Run `tests/apply/test_loading.py` after T003–T004 and fix any foundation regressions in `rapyuta_io_sdk_v2/apply/_loader.py` before starting story work.
- [X] T006 Implement the shared CLI-oracle capture tool in `scripts/capture_apply_parity.py`: read checked in case descriptors, invoke the rio CLI local Apply parser, support `--suite rio-filters|ansible-filters|charts` (omitted means all), `--write`, and read-only `--verify`; capture successful documents and expected CLI failures by case ID, exception type, and message, and replay both during verification; record source/input hashes, capture command, explicit rio/environment/device inputs, and actual Python, Ansible, Jinja, and CLI versions; require exact recorded Python/Ansible/Jinja versions and CLI revision during verification, rejecting drift before rendering or writing; use controlled environment/device inputs without platform requests. Chart source copying is added in US3.

**Checkpoint**: The prior manifest loading contract still passes, and both direct-filter stories have a shared CLI capture and replay tool.

---

## Phase 3: User Story 1 - Render manifests with rio filters (Priority: P1) 🎯 MVP

**Goal**: Existing `getenv` and `get_intf_ip` expressions render with the CLI's names, argument order, and observable results in both SDK facades.

**Independent Test**: Use controlled CLI reference outputs and manifests containing each filter; verify set/unset/empty environment values, positional and named interface arguments, interface preference, source-aware failures, and offline non-device rendering through `Applier` and `AsyncApplier`.

### Tests for User Story 1

- [X] T007 [US1] Define standalone rio filter manifests and set/unset/empty environment, positional/keyword interface, project, and controlled device-response cases in `tests/apply/fixtures/parity/rio-filters/cases.yaml`, including `get_intf_ip` with no candidate address; align the CLI capture Python/Ansible/Jinja versions with the SDK test environment, stub only the CLI device information provider for device cases, run `scripts/capture_apply_parity.py --suite rio-filters --write` under the pinned CLI checkout, and check in its CLI-rendered `tests/apply/fixtures/parity/rio-filters/outputs.yaml`, `errors.json`, and `provenance.json` before writing SDK expectations. Confirm `--suite rio-filters --verify` reproduces both successful documents and the no-address CLI failure from recorded inputs without a platform account.
- [X] T008 [P] [US1] Write failing CLI-oracle contract tests in `tests/apply/test_filters.py` using existing `inspect().resolved_manifests` fields for `getenv(default, env_var)` and `get_intf_ip(device_name, interface)` with positional and `interface=` forms, first nonempty candidate/first address, and invalid arguments; do not depend on US3's new inspection field.
- [X] T009 [P] [US1] Write failing preparation tests in `tests/apply/test_loading.py` for missing project scope/resolver, lookup or unreadiness error, no available address, mismatched `rio.project.guid`, and proof that files without `get_intf_ip` never call the resolver or platform; for no available address, use `tests/apply/fixtures/parity/rio-filters/errors.json` to assert the SDK failure identifies the same device and requested interface list while retaining SDK source attribution, without requiring identical CLI and SDK exception text.

### Implementation for User Story 1

- [X] T010 [US1] Add the public `DeviceInterfaceResolver` callable Protocol and optional `ManifestSource.interface_resolver` field in `rapyuta_io_sdk_v2/apply/source.py`; enforce the contract: synchronous `(project_guid: str, device_name: str) -> Mapping[str, Sequence[str]]`, held by reference, omitted unless `get_intf_ip` is evaluated.
- [X] T011 [US1] Implement rio `getenv` and `get_intf_ip` registration in `rapyuta_io_sdk_v2/apply/_filters.py`; preserve present empty environment values, comma-separated candidate order, and the first address of the first interface with a nonempty first address, matching the CLI.
- [X] T012 [US1] Pass `ManifestSource.interface_resolver` and explicit project scope through `rapyuta_io_sdk_v2/apply/_loader.py`; require both only when `get_intf_ip` executes, validate resolver mapping/address shape and optional `rio.project.guid` agreement, and wrap failures with the manifest source and `template` category.
- [X] T013 [US1] Pass `ApplierOptions.scope` into shared preparation from `rapyuta_io_sdk_v2/apply/applier.py` for sync and async facades, and export the resolver type through `rapyuta_io_sdk_v2/__init__.py` without changing call-time client ownership.
- [X] T014 [US1] Run `tests/apply/test_filters.py` and `tests/apply/test_loading.py`; confirm T008–T009 pass and existing strict undefined, resource preparation, and offline inspection tests remain green.

**Checkpoint**: Rio filter manifests are independently renderable and testable without Ansible-specific expressions or chart fixtures.

---

## Phase 4: User Story 2 - Reuse Ansible filter expressions (Priority: P1)

**Goal**: SDK Apply supports the same five registered Ansible filter groups as the CLI and keeps Jinja's built in `default` behavior.

**Independent Test**: Prepare controlled expressions from every group against CLI reference values, including a deterministic encryption case and an undefined value with `default`; verify bad filters fail before apply/delete.

### Tests for User Story 2

- [X] T015 [US2] Define standalone Ansible `combine`, `urldecode`, `urlsplit`, `log`, `vault`/`unvault` (fixed salt and synthetic secret), and Jinja `default` cases in `tests/apply/fixtures/parity/ansible-filters/cases.yaml`; align the CLI capture Python/Ansible/Jinja versions with the SDK test environment, run `scripts/capture_apply_parity.py --suite ansible-filters --write` under the pinned CLI checkout, and check in its CLI-rendered `tests/apply/fixtures/parity/ansible-filters/outputs.yaml` and `provenance.json` before writing SDK expectations. Confirm `--suite ansible-filters --verify` reproduces the structured output from the recorded inputs without a platform account.
- [X] T016 [P] [US2] Add failing filter-group parity assertions to `tests/apply/test_filters.py` using T015's CLI reference and existing `inspect().resolved_manifests` fields, covering names, piped input, positional/named arguments, and the untouched Jinja `default('fallback')` behavior; do not depend on US3's new inspection field.
- [X] T017 [P] [US2] Add failing source-attribution tests in `tests/apply/test_loading.py` for unknown filters, invalid Ansible arguments, and simulated Ansible import/initialization failure, proving no apply/delete request begins.

### Implementation for User Story 2

- [X] T018 [US2] Register Ansible `core`, `urls`, `urlsplit`, `mathstuff`, and `encryption` filter maps in CLI order in `rapyuta_io_sdk_v2/apply/_filters.py`; skip core `default`, avoid silent partial registration, and leave `StrictUndefined` and sandbox behavior intact.
- [X] T019 [US2] Run `tests/apply/test_filters.py` and `tests/apply/test_loading.py`; confirm T016–T017 pass with installed Ansible support and no regressions in User Story 1.

**Checkpoint**: Ansible expressions are independently testable with static CLI reference data; ordinary tests do not import the CLI.

---

## Phase 5: User Story 3 - Detect parity regressions with chart fixtures (Priority: P1)

**Goal**: Compare SDK rendered documents with CLI-generated outputs for two distinct cases each from postgis, gateway, and gostproxy.

**Independent Test**: Run six fixture cases with checked in chart templates and values. Confirm document counts/order, keys, list order, scalar types, changed branches, sync/async equivalence, and reproducible CLI provenance without a platform account.

### Chart input and CLI oracle preparation

- [X] T020 [P] [US3] Define `postgis/base` from tracked `values.sample.yaml` and `postgis/standby` with standby enabled plus one changed database field in `tests/apply/fixtures/parity/postgis/cases.yaml`; select all tracked `incubator/postgis/templates/*.yaml` files and expect 2 versus 4 documents.
- [X] T021 [P] [US3] Define `gateway/base` from tracked `values.yaml` and `gateway/toxiproxy` with synthetic version and one enabled service in `tests/apply/fixtures/parity/gateway/cases.yaml`; select all tracked `incubator/gateway/templates/*.yaml` files and expect 2 versus 4 documents.
- [X] T022 [P] [US3] Define `gostproxy/direct-ip` with a synthetic VPN IP and `gostproxy/interface-ip` with empty VPN IP, candidate interfaces, a controlled two-address response, and changed route suffix in `tests/apply/fixtures/parity/gostproxy/cases.yaml`; select all tracked `incubator/gostproxy/templates/*.yaml` files and expect 3 versus 4 documents.
- [X] T023 [US3] Extend the shared `scripts/capture_apply_parity.py` tool's `--suite charts` path to copy only tracked chart templates, stub only the CLI device information provider for the interface case, reject untracked inputs, and record chart revision/source hashes without platform or chart-host requests; preserve direct-filter capture and verification behavior.
- [X] T024 [US3] Align the CLI capture environment's installed Python/Ansible/Jinja versions with the SDK test environment, run `scripts/capture_apply_parity.py --suite charts --write` before SDK comparison, and check in ordered CLI output YAML, copied templates, complete case values, and `tests/apply/fixtures/parity/provenance.json`; verify the six expected document counts, no production credentials, and successful read-only `--suite charts --verify` replay.

### Tests for User Story 3

- [X] T025 [P] [US3] Write failing six-case tests in `tests/apply/test_chart_parity.py` that load T024's CLI outputs and compare SDK raw documents for both facades with recursive type-sensitive equality; ignore only mapping key order/YAML formatting, report chart/case/document/path on mismatch, and assert zero network/platform requests.
- [X] T026 [P] [US3] Write failing inspection-contract tests in `tests/apply/test_loading.py` for input order, omission of empty YAML documents, file `source` attribution, deep-copy isolation, and resource-instance representation alongside unchanged `resolved_manifests`.

### Implementation for User Story 3

- [X] T027 [US3] Add public Pydantic `RenderedDocument(source: SourceLocation, data: dict[str, Any])` and `InspectionResult.rendered_documents: tuple[RenderedDocument, ...] = ()` in `rapyuta_io_sdk_v2/models/applier.py`; for file inputs `data` is the deep copied parsed document before model normalization, while caller supplied resource instances use a deep copied model representation.
- [X] T028 [P] [US3] Populate `InspectionResult.rendered_documents` from deep copies of ordered `PreparedResource.source_data` in `rapyuta_io_sdk_v2/apply/applier.py`, preserving the existing validated `resolved_manifests` output and both facade behaviors.
- [X] T029 [P] [US3] Export `RenderedDocument` from `rapyuta_io_sdk_v2/__init__.py` and verify the public import contract without adding API-client operations.
- [X] T030 [US3] Run `tests/apply/test_chart_parity.py` and `scripts/capture_apply_parity.py --verify` for all three fixture suites against the pinned CLI/chart checkouts; resolve only real parity differences and confirm fixtures stay unchanged during verification.

**Checkpoint**: All six chart cases match their CLI fixtures, including both gostproxy device-address branches.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Document the public contract and pass project-wide checks.

- [X] T031 Update `README.md` with a short `ManifestSource.interface_resolver`, explicit project scope, Ansible availability, and `inspect().rendered_documents` example; link to `specs/002-apply-render-parity/quickstart.md` for fixture validation.
- [X] T032 Review `specs/002-apply-render-parity/contracts/sdk-rendering.md` and `specs/002-apply-render-parity/contracts/fixture-provenance.md` against the implemented interfaces, actual fixture metadata, and constitution; correct any drift without weakening acceptance requirements.
- [X] T033 Add `tests/apply/test_capture_apply_parity.py` unit cases using temporary fixture directories and a stubbed CLI parser/version probe: vary each recorded Python, Ansible, and Jinja version and CLI revision independently and assert `--verify` rejects every mismatch before rendering or writing; assert matching metadata verifies rio success and expected-failure records, Ansible, and chart fixture sets without file changes or sibling checkouts.
- [X] T034 Run the commands in `specs/002-apply-render-parity/quickstart.md`, including all `tests/apply/` tests and pinned Ruff 0.16.9 check/format gates; fix failures in the touched `rapyuta_io_sdk_v2/apply/`, `rapyuta_io_sdk_v2/models/applier.py`, `tests/apply/`, and `scripts/capture_apply_parity.py` files.

---

## Dependencies & Execution Order

### Phase dependencies

```text
Setup T001–T002
      │
      ▼
Foundation T003–T006
      ├────────► US1 T007–T014 ────────┐
      ├────────► US2 T015–T019 ────────┤
      └────────► US3 inputs T020–T024  │
                                       ▼
                             US3 tests/implementation T025–T030
                                       │
                                       ▼
                               Polish T031–T034
```

- T001 and T002 are independent setup work. T003 depends on setup; T004 depends on T003; T005 validates the rendering foundation. T006 establishes CLI fixture capture and verification before T007 or T015.
- US1 and US2 direct fixture capture/tests can begin after T006. Their edits to `tests/apply/test_filters.py`, `tests/apply/test_loading.py`, and `rapyuta_io_sdk_v2/apply/_filters.py` must be serialized or merged deliberately if different people work at once.
- US3 input definitions and chart capture can begin after T006 and proceed alongside filter implementation. Complete US1 and US2 before treating US3's full six-case parity result as done; `gostproxy/interface-ip` requires US1 and the shared registry requires US2.
- Polish follows all three story checkpoints.

### Within each story

- US1: T007 → T008/T009 (parallel) → T010 → T011 → T012 → T013 → T014.
- US2: T015 → T016/T017 (parallel) → T018 → T019. T018 shares `_filters.py` with T011, so serialize those edits.
- US3: T020/T021/T022 (parallel) → T023 → T024 → T025/T026 (parallel) → T027 → T028/T029 (parallel) → T030.
- Polish: T031/T032 → T033 → T034; T033 uses temporary fixture data and a stubbed parser so ordinary tests stay offline.
- Run each story's failing tests before its implementation tasks; keep CLI oracle files read-only during SDK comparisons.

## Parallel Execution Examples

### User Story 1

After T007, T008 can cover exact filter results in `tests/apply/test_filters.py` while T009 covers preparation errors and no-lookup behavior in `tests/apply/test_loading.py`.

### User Story 2

After T015, T016 can cover all five Ansible groups in `tests/apply/test_filters.py` while T017 covers import and argument failures in `tests/apply/test_loading.py`.

### User Story 3

T020, T021, and T022 can define case values in separate chart directories. After T024, T025 can build the chart comparison in `tests/apply/test_chart_parity.py` while T026 covers inspection guarantees in `tests/apply/test_loading.py`. After T027, T028 and T029 touch separate runtime files.

## Implementation Strategy

### MVP: User Story 1

Complete setup and foundation, capture the rio filter CLI oracle, write failing US1 tests, implement the resolver and rio filters, then pass T014. This delivers manifest-level rio filter compatibility without relying on chart fixtures.

### Incremental delivery

Add US2 with independently captured Ansible reference cases. Prepare US3 case inputs and CLI outputs concurrently where practical, then add public raw inspection and run the complete chart parity suite. Finish with documentation and the full project gates.

## Notes

- No Client/AsyncClient API operation or platform payload model changes are planned.
- `ANSIBLE_LOCAL_TEMP` must point to a writable path when Ansible initializes in restricted test environments.
- Static CLI fixtures are the oracle. An implementation must not refresh them from SDK output to make a test pass.

## Phase 7: Convergence

- [X] T035 Ensure `scripts/capture_apply_parity.py` imports the rio CLI parser and filters from the selected `--cli-root` checkout, rejects an ambient installed CLI that would shadow that checkout, and tests import precedence and revision attribution per SC-004 (partial).
- [X] T036 Replace the CLI device information provider for every capture case so a missing controlled response fails locally without a platform lookup; test a device expression without recorded device data and preserve replay of the existing controlled cases per US3/AC4 (partial).
- [X] T037 Compare successful CLI replay documents recursively with scalar type sensitivity in `scripts/capture_apply_parity.py --verify`; add offline capture-tool tests showing that bool/int, int/float, and sequence-order drift are rejected without fixture writes per SC-004 (partial).

## Phase 8: Convergence

- [X] T038 Make `tests/apply/test_chart_parity.py` compare mapping keys by both type and value without depending on key order; add regression tests proving bool/int and int/float key drift is reported while existing value, document-order, and sequence-order checks remain intact per FR-009 and T025 (partial).
