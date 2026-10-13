---

description: "Implementation tasks for Configtree Import and Fast Merge"
---

# Tasks: Configtree Import and Fast Merge

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, and `quickstart.md` in `specs/001-configtree-import-merge/`

**Tests**: The specification defines independent tests for every story and measurable acceptance outcomes; the tasks below create focused automated evidence for them.

**Organization**: P1 stories are ordered by implementation dependency: the Revision context (US3), Import (US1), then Merge (US2). P2 parity and failure coverage (US4) follows. Each story has its own acceptance checkpoint.

## Format: `[ID] [P?] [Story] Description`

- `[P]` means the task can proceed alongside other marked tasks in its phase because it touches separate files and does not depend on unfinished tasks.
- Story labels map to the IDs in `spec.md`; setup, foundation, and polish tasks have no story label.
- Paths are relative to the repository root.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the new helper package and reusable transport fixture without changing dependencies or client ownership.

- [X] T001 Create `rapyuta_io_sdk_v2/configtree/__init__.py` as the public package entry point, with an initial module docstring and no client workflow methods.
- [X] T002 [P] Create `tests/utils/configtree_operations.py` with a stateful HTTPX MockTransport fixture that records scoped get/list/create/batch/commit/head requests and can inject stage failures for both clients.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define shared options, errors, routing, lifecycle support, and the relevant low-level async request contract before story work.

- [X] T003 [P] Define `RevisionOptions`, `ImportOptions`, `MergeOptions`, and recursive `ConfigContent` in `rapyuta_io_sdk_v2/models/configtree_operations.py` under these data-model constraints: `RevisionOptions` has "with_project=True", "commit=False", "commit_body=None" and "Frozen helper options"; `ImportOptions` has "all RevisionOptions fields plus update_head=False"; `MergeOptions` has "with_project=True", "commit_body=None" and "Merge always commits and updates the head; these actions cannot be disabled"; deep-copy nested commit bodies into execution state.
- [X] T004 [P] Define `ConfigTreeInputError`, `ConfigTreeReferenceError`, `ConfigTreeMergeConflictError`, and `ConfigTreeMutationError` with contextual fields and the contract's `ValueError`/`RuntimeError` bases in `rapyuta_io_sdk_v2/configtree/exceptions.py`; keep messages free of imported values.
- [X] T005 [P] Implement immutable organization/project scope snapshots in `rapyuta_io_sdk_v2/configtree/_scope.py`: require organization context, require project context for project operations, pass explicit per-call GUIDs and `with_project=False` for org scope, and never alter client configuration.
- [X] T006 Export the options models and `ConfigContent` from `rapyuta_io_sdk_v2/models/__init__.py`, preserving existing exports.
- [X] T007 Implement commit-body preparation and exception recovery annotation in `rapyuta_io_sdk_v2/configtree/_lifecycle.py`: fill missing author from configured email or `rapyuta-io-sdk-v2`, fill missing direct-context message with `Created revision through rapyuta-io-sdk-v2` or the Import/Merge operation default, reject explicit blank author/message before creation, retain labels, and annotate original errors with known revision ID and `prepare`/`resolve`/`create`/`body`/`validate`/`store`/`commit`/`head` stage.
- [X] T008 [P] Add request-contract tests for the canonical revision batch URL and omission of absent tree selectors/filters in `tests/async_tests/test_configtree_async.py`, asserting response model validation and query/header behavior.
- [X] T009 Correct `AsyncClient.put_keys_in_revision` to `PUT /v2/configtrees/{name}/revisions/{revision_id}/` and make `AsyncClient.get_configtree` omit absent optional query fields in `rapyuta_io_sdk_v2/async_client.py`, preserving aliases, typed responses, and awaited I/O.

**Checkpoint**: Shared contracts and scoped transport behavior are ready; T008 passes after T009.

---

## Phase 3: User Story 3 - Edit Pending Revision Keys and Store Them Together (Priority: P1)

**Goal**: Users can edit one live per-context dictionary and submit its validated final contents in a single batch, optionally followed by commit.

**Independent Test**: In sync and async contexts, add/replace entries, edit metadata, remove a pending entry, and confirm the final batch contains exactly the remaining entries. Confirm empty and exceptional exits issue zero key writes.

### Tests for User Story 3

- [X] T010 [P] [US3] Add encoding and strict snapshot tests in `tests/test_configtree_helpers.py` for Unicode byte length, base64/MD5 consistency, `kv`/`644`, explicit `{}` metadata, invalid direct mutations, missing data, malformed or non-UTF-8 key paths, and unchanged omitted fields.
- [X] T011 [P] [US3] Add synchronous context tests in `tests/sync_tests/test_configtree_operations.py` for dictionary identity/isolation, add/replace/edit/remove/clear, one or zero batch calls, optional commit order and the direct-context default message, body abort, failed acknowledgement, and single-use entry.
- [X] T012 [P] [US3] Add asynchronous context tests in `tests/async_tests/test_configtree_operations_async.py` for the same final dictionary and batch contract, snapshot before awaited storage, body cancellation, and cancellation during create/store/commit with no later stage.
- [X] T013 [P] [US3] Extend `tests/test_model_contracts.py` to verify `ConfigValues` root serialization, `ConfigValue` aliases and field presence, explicit empty metadata versus omitted metadata, and rejection of invalid plain-field snapshots despite mutable existing model instances.

### Implementation for User Story 3

- [X] T014 [US3] Implement logical leaf encoding and independent strict `ConfigValue`/`ConfigValues` snapshots in `rapyuta_io_sdk_v2/configtree/_values.py`: honor "UTF-8/base64 data, MD5 artifact checksum, byte count, `content_type=\"kv\"`, and default permissions `\"644\"`"; validate "nonempty string key paths with no empty segments or surrounding whole-key whitespace, present base64 key-value data, required content type/checksum and content length, and compatible field types"; require checksum and declared length to match decoded bytes, preserve `exclude_unset` and valid Merge fields without repair, and identify the bad key without tightening low-level models.
- [X] T015 [US3] Implement `Revision` in `rapyuta_io_sdk_v2/configtree/revision.py`: local construction; one `create_revision` on entry with optional pinned parent; getter-only, stable `dict[str, ConfigValue]` and synchronous `store()`; valid GUID capture; on normal exit one nonempty batch or zero empty writes, require `APIResponse.success=True` with no nonempty `error`, optionally commit, and never select head; exceptional exit skips finalization and retains original annotated error.
- [X] T016 [US3] Implement `AsyncRevision` in `rapyuta_io_sdk_v2/configtree/revision.py` with the same local staging and single-use contract, awaited create/batch/commit, snapshot before the first storage await, and unshielded `CancelledError` propagation with known recovery ID/stage.
- [X] T017 [US3] Export `Revision`, `AsyncRevision`, `RevisionOptions`, and relevant domain errors from `rapyuta_io_sdk_v2/configtree/__init__.py` with typed public docstrings covering inputs, result, and failure behavior.

**Checkpoint**: T010–T013 pass with no per-key requests; both contexts can be used independently of Import and Merge.

---

## Phase 4: User Story 1 - Import Configuration Documents (Priority: P1)

**Goal**: Import mixed named JSON/YAML files into one new destination revision, with independent commit and head choices.

**Independent Test**: Import `robot.json` and `site.yaml` into an existing tree; inspect prefixed values and exact metadata, returned revision ID, batch count, commit state, and head for all four option combinations. Invalid inputs must fail before creation.

### Tests for User Story 1

- [X] T018 [P] [US1] Add document tests in `tests/test_configtree_helpers.py` for three `.json`/`.yaml`/`.yml` files in one import, final-suffix stems, slash flattening, lists and empty nested objects as leaves, ISO dates, metadata wrapper boundaries and exact-path attachments, plus empty documents and mapping roots yielding no keys, duplicate keys/stems, ambiguous paths, malformed or unsafe input, invalid metadata, and sanitized file/key errors.
- [X] T019 [P] [US1] Add synchronous Import transport tests in `tests/sync_tests/test_configtree_operations.py` for four commit/head combinations, one revision and batch, inheritance of unrelated keys, unusable parent failure, ordering, returned GUID, and zero create requests for empty documents or mapping roots producing no keys.
- [X] T020 [P] [US1] Extend `tests/sync_tests/test_pydantic_source.py` to preserve existing settings-source local parsing, flattening, and wrapper removal when the shared metadata splitter is used.

### Implementation for User Story 1

- [X] T021 [US1] Implement duplicate-aware UTF-8 JSON and safe single-document YAML parsing in `rapyuta_io_sdk_v2/configtree/_documents.py`: require a nonempty iterable of named files with mapping roots; honor "Supported suffixes are `.json`, `.yaml`, and `.yml`" and "duplicate stems are invalid"; reject empty documents and mapping roots yielding zero flattened keys, duplicate explicitly authored mapping keys, non-UTF-8 path components, cycles, non-finite or unsupported values, while preserving YAML merge override precedence and reporting file/location without content before any mutation.
- [X] T022 [US1] Implement rio-style wrapper splitting and deterministic flattening in `rapyuta_io_sdk_v2/configtree/_documents.py`: recognize a "mapping-valued child with exactly `value` and `metadata`, where the latter is a dictionary"; honor "Ordinary mapping children are traversed; wrapper values and lists are not traversed during splitting"; retain empty attachments, validate `dict[str, str]`, reject empty/non-string/slash-ambiguous content paths, and join attachments "only at identical final paths".
- [X] T023 [US1] Reuse the shared content-only splitter from `rapyuta_io_sdk_v2/configtree/_documents.py` in `rapyuta_io_sdk_v2/pydantic_source/source.py::_split_metadata`, leaving its existing parser, flattening, and settings inputs unchanged.
- [X] T024 [US1] Implement synchronous `import_configtree` in `rapyuta_io_sdk_v2/configtree/workflows.py`: materialize and prepare every file before create, verify target and usable current head in selected scope, stage typed keys through `Revision`, use the import commit default, optionally select head only after successful exit, and return the new GUID or propagate an original error annotated with its ID/stage.
- [X] T025 [US1] Export `ImportOptions` and `import_configtree` from `rapyuta_io_sdk_v2/configtree/__init__.py` with typed public documentation, including the platform's possible rejection of uncommitted head selection.

**Checkpoint**: T018–T020 pass. This is the synchronous Import increment; the full dual-mode feature requires US4.

---

## Phase 5: User Story 2 - Fast Merge a Referenced Tree Revision (Priority: P1)

**Goal**: Resolve a source refspec and merge compatible key-value entries into a fresh committed destination revision without prompts.

**Independent Test**: Merge disjoint and identical shared keys from a scoped source, inspect the one committed destination revision and head, then repeat with conflicting data or metadata and verify all conflict names appear before any destination creation.

### Tests for User Story 2

- [X] T026 [P] [US2] Add pure refspec and merge-map tests in `tests/test_configtree_helpers.py` for all six accepted forms, invalid components, stored data/metadata equality, absent versus `{}` metadata, sorted complete conflict names, source-only payload preservation, rejection of absent or stale source content length including shared keys, and valid empty maps.
- [X] T027 [P] [US2] Add synchronous Merge transport tests in `tests/sync_tests/test_configtree_operations.py` for scoped head/explicit revision/milestone selection, later-page duplicate milestones, returned revisions with a mismatched milestone label, and bad tokens; cover both cross-scope directions, source immutability, pinned parent, compatible/empty/same-tree merges, and zero destination mutation on reference, conflict, or a multibyte source key with stale content length.
- [X] T028 [P] [US2] Extend `tests/sync_tests/test_configtree.py` to assert explicit organization/project header selection and typed request/response contracts for the six existing low-level operations used by Merge.

### Implementation for User Story 2

- [X] T029 [US2] Implement `ConfigTreeRef` and `parse_refspec` in `rapyuta_io_sdk_v2/configtree/_refs.py` using the exact data-model shape "Immutable four-field tuple with `is_org: bool`, `tree_name: str`, `revision_id: str or None`, and `milestone: str or None`"; accept only `org/<tree>[/<selector>]` or `proj/<tree>[/<selector>]`, reject blank/extra components without trimming, and apply "Selectors beginning with `rev-` are revision IDs; all others are milestones".
- [X] T030 [US2] Implement synchronous scoped source resolution in `rapyuta_io_sdk_v2/configtree/_refs.py`: read head or explicit revision with `include_data=True` and `content_types=["kv"]`, paginate milestone label `rapyuta.io/milestone=<name>` with `committed=False`, verify the actual label on every returned candidate before counting distinct valid GUIDs, require advancing positive numeric continuation with zero ending pagination, and reject an omitted or null whole key map before revision creation.
- [X] T031 [US2] Implement compatible key-map union in `rapyuta_io_sdk_v2/configtree/_values.py`: before creation validate every selected source entry has a present content length equal to its decoded byte count and report an inconsistent key without changing the source payload; then require selected entries' data, compare shared stored `data` and field-preserving `metadata`, retain destination entries on equality, deep-copy source-only payloads without re-encoding, and report every sorted conflicting key.
- [X] T032 [US2] Implement synchronous `merge_configtree` in `rapyuta_io_sdk_v2/configtree/workflows.py`: snapshot source/destination scopes, validate destination head as a usable committed parent, resolve/read both selected revisions, compute union before mutation, create through `Revision(parent=checked_head)`, submit one batch if nonempty, commit with merge defaults, select the new head, and return GUID without rereading or retrying after a concurrent head change.
- [X] T033 [US2] Export `MergeOptions`, `ConfigTreeRef`, `parse_refspec`, and `merge_configtree` from `rapyuta_io_sdk_v2/configtree/__init__.py` with typed public documentation and conflict/reference errors.

**Checkpoint**: T026–T028 pass; US2 creates one committed revision even for an identical or empty union and makes no source mutation.

---

## Phase 6: User Story 4 - Use Either Execution Mode Reliably (Priority: P2)

**Goal**: Provide asynchronous Import and Merge with the same results and recovery behavior as the synchronous workflows.

**Independent Test**: Run Import and Merge acceptance cases in both modes and compare keys, metadata, commit state, head, and error classes apart from generated IDs. Inject failures at create, storage, commit, and head, then cancel async work at each await boundary.

### Tests for User Story 4

- [X] T034 [P] [US4] Extend `tests/async_tests/test_configtree_operations_async.py` with Import and Merge parity scenarios, including async file preparation, four Import publication combinations, all six refspec forms, paginated milestones with mismatched returned labels, compatible/conflicting/empty unions, source-length rejection before creation, and cross-scope routing.
- [X] T035 [P] [US4] Extend `tests/sync_tests/test_configtree_operations.py` with body, validation, unsuccessful envelope, transport, commit, and head failures; assert no later stage and original error type plus known revision ID/stage.
- [X] T036 [US4] Extend `tests/async_tests/test_configtree_operations_async.py` with matching failure and cancellation injections at create, store, commit, and head; assert `CancelledError` survives, no later request starts, and known IDs/stages remain recoverable.

### Implementation for User Story 4

- [X] T037 [US4] Add asynchronous scoped source/milestone resolution to `rapyuta_io_sdk_v2/configtree/_refs.py`, using awaited client reads and the same exact returned-label verification, identity, pagination, empty-map, and reference-failure rules as T030.
- [X] T038 [US4] Implement `import_configtree_async` in `rapyuta_io_sdk_v2/configtree/workflows.py`: prepare local documents through `asyncio.to_thread`, use awaited scoped reads and `AsyncRevision`, then await optional head selection after context success; preserve original errors and unshielded cancellation with ID/stage annotations.
- [X] T039 [US4] Implement `merge_configtree_async` in `rapyuta_io_sdk_v2/configtree/workflows.py`: use awaited scoped reads and T037 resolution, compute the same pre-create union as sync Merge, use `AsyncRevision(parent=checked_head)`, then await head selection; preserve cancellation and stage recovery without retry/rollback.
- [X] T040 [US4] Export `import_configtree_async` and `merge_configtree_async` from `rapyuta_io_sdk_v2/configtree/__init__.py`, documenting their typed interfaces and cancellation behavior.

**Checkpoint**: T034–T036 pass with sync/async semantic parity and no later publication stage after failure.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Make the public workflow usable and run the full repository gates.

- [X] T041 [P] Document synchronous/asynchronous Import, Merge, `Revision.keys`, options, refspecs, recoverable failures, and concurrent-head limits with executable examples in `README.md`.
- [X] T042 Validate the focused acceptance commands and public import smoke check from `specs/001-configtree-import-merge/quickstart.md`; correct that guide's focused test path to the created `tests/test_configtree_helpers.py` if needed.
- [X] T043 Run `uv run pytest tests/ --cov` under Python 3.13 and 3.14, then `uvx ruff==0.16.9 check .` and `uvx ruff==0.16.9 format --check .` against the implementation; fix any feature-related failures in their reported files and record both interpreter results and Ruff results in `specs/001-configtree-import-merge/quickstart.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** starts immediately.
- **Foundation (Phase 2)** follows setup and blocks all story phases; T009 follows T008's contract test.
- **US3 (Phase 3)** follows foundation and supplies both Revision contexts and batch validation.
- **US1 (Phase 4)** follows US3; its Import workflow uses `Revision` and `_values.py`.
- **US2 (Phase 5)** follows US3 and can proceed alongside US1 once its own source files/tests are coordinated; both append to `workflows.py` and package exports, so those edits must be serialized.
- **US4 (Phase 6)** follows US1 and US2 because it adds async counterparts to both workflows.
- **Polish (Phase 7)** follows the desired story scope; full regression and Ruff gates follow implementation and focused checks.

### User Story Dependencies

- **US3 (P1)**: No story dependency; independently usable Revision/AsyncRevision context.
- **US1 (P1)**: Depends on US3's context and encoding; independently verifiable as an Import workflow.
- **US2 (P1)**: Depends on US3's context and validation; its refspec and compatibility behavior are independently verifiable.
- **US4 (P2)**: Depends on US1 and US2 to compare sync and async workflows.

### Within Each User Story

- Write the listed acceptance tests first, then implement the models/pure helpers, client composition, and exports in task order.
- A task that modifies the same file as another task runs after that earlier task even when their story phases could otherwise overlap.
- Complete each story's independent checkpoint before claiming that story delivered.

### Parallel Opportunities

- T001 and T002 are independent setup files.
- T003, T004, and T005 can be written in parallel; T006 follows T003 and T007 follows their shared contracts.
- The distinct test files in T010–T013, T018–T020, and T026–T028 can be authored in parallel within their stories. Shared helper/test files across stories are edited in story order.
- T034 and T035 can be authored in parallel; T036 extends T034's file afterward.
- T041 can proceed alongside story verification once public behavior is stable.

## Parallel Example: User Story 3

```text
T010: tests/test_configtree_helpers.py — pure encoding/snapshot cases
T011: tests/sync_tests/test_configtree_operations.py — sync context cases
T012: tests/async_tests/test_configtree_operations_async.py — async context cases
T013: tests/test_model_contracts.py — wire-preservation cases
```

## Parallel Example: User Story 1

```text
T018: tests/test_configtree_helpers.py — document and wrapper cases
T019: tests/sync_tests/test_configtree_operations.py — Import publication cases
T020: tests/sync_tests/test_pydantic_source.py — settings-source regression cases
```

## Parallel Example: User Story 2

```text
T026: tests/test_configtree_helpers.py — refspec and union cases
T027: tests/sync_tests/test_configtree_operations.py — Merge workflow cases
T028: tests/sync_tests/test_configtree.py — low-level scope contracts
```

## Parallel Example: User Story 4

```text
T034: tests/async_tests/test_configtree_operations_async.py — async parity cases
T035: tests/sync_tests/test_configtree_operations.py — sync failure cases
```

## Implementation Strategy

### First Synchronous Increment

1. Complete Setup and Foundation.
2. Complete US3 and verify its independent context checkpoint.
3. Complete US1 and verify mixed-file synchronous Import with all four publication options. The full feature also requires US2 and US4.

### Incremental Delivery

1. Add US2 and verify compatible/conflicting scoped merges independently.
2. Add US4 and verify async parity, stage failures, and cancellation.
3. Complete documentation, full regression, and Ruff gates in Phase 7.

### Parallel Team Strategy

After US3 is complete, one worker can prepare US1 document handling and another US2 refspec/union handling. Coordinate `workflows.py`, `_values.py`, `tests/test_configtree_helpers.py`, and package exports as serial integration points. The distinct story test files identified above can be written concurrently within each phase.

## Phase 8: Convergence

- [X] T044 Report sanitized parser line and column when available in `rapyuta_io_sdk_v2/configtree/_documents.py` and `ConfigTreeInputError`, prevent raw JSON/YAML parser context from appearing in error details or tracebacks, and test malformed input with a sensitive value per FR-003 (partial).
- [X] T045 Align Import component validation in `rapyuta_io_sdk_v2/configtree/_documents.py` with the final key-path contract so valid internal spaces are accepted while empty, whitespace-only, slash-containing, or whole-key-invalid paths still fail; add focused document tests per FR-004 (partial).

## Phase 9: Convergence

- [X] T046 Run the current full SDK test and coverage suite under Python 3.14, confirm the Python 3.13 and Ruff results for the current implementation, and refresh the validation record in `specs/001-configtree-import-merge/quickstart.md` per T043 (partial).
