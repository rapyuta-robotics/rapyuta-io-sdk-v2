# Feature Specification: Configtree Import and Fast Merge

**Feature Branch**: `feat/configtrees`

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "Provide higher-level Configtree Import and non-interactive fast Merge, synchronously using Client and asynchronously using AsyncClient. Import one or more JSON/YAML documents, flatten their keys with each filename without its suffix as a prefix, and create a new revision, optionally committing it and setting the tree head. Merge accepts org/proj tree refspecs with an optional revision ID or milestone. Use the Revision context manager and restrict scope to Import and Merge."

**Additional Input**: "Replicate the Metadata splitting logic for the Keys from the rio CLI for importing. Also in the revision context manager, expose the key-value dictionary and let users modify it. Then use batch operations when creating the Revision."

## Clarifications

### Session 2026-10-12

- Q: If another writer changes the destination tree's head while Merge is running, should Merge still publish its revision based on the head it originally read? → A: Yes. Merge uses the originally read head as its parent and may select its new revision as head even if another writer has changed the head meanwhile; callers needing strict ordering must coordinate writers.
- Q: If someone edits encoded key data directly in the revision's public dictionary but leaves its checksum or size out of date, what should happen when the revision is saved? → A: Reject the inconsistent entry before batch submission and identify its key.
- Q: If the destination tree's current head is uncommitted and the platform cannot use it as a parent, should Import or Merge fail instead of choosing a different parent? → A: A tree head cannot be uncommitted under platform rules. For any other unusable existing head or parent, fail explicitly without choosing a fallback parent or advancing the head.
- Q: When an imported JSON or YAML file is invalid, how much of its content may an error message include? → A: Report the affected file and, when known, the key or location, without including imported values or credentials.
- Q: If a caller changes the public key dictionary after an asynchronous revision starts saving it, should those late edits affect the batch already being submitted? → A: Supported edits occur inside the context body. Retained references used after the body exits, including during finalization, have unspecified behavior; add no special prevention mechanism.

### Session 2026-10-13

- Q: If a source key's recorded content length differs from its decoded byte length, should Merge reject it before creating a destination revision? → A: Yes. Reject the inconsistent source entry, identify its key, and create no destination revision; do not change the source payload or recalculate its length.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import Configuration Documents (Priority: P1)

As an SDK user, I want to import configuration files into one new tree revision so that my application can publish configuration without manually managing individual keys.

**Why this priority**: Import is the primary path from existing local configuration to a reusable Configtree revision.

**Independent Test**: Import a JSON file and a YAML file into an existing tree. Inspect the resulting revision, its prefixed keys, its commit status, and the tree head. Repeat with each publication option.

**Acceptance Scenarios**:

1. **Given** `robot.json` containing `{"navigation": {"speed": 2}}` and `site.yaml` containing `region: east`, **When** the user imports both, **Then** exactly one new revision contains `robot/navigation/speed` with value `2` and `site/region` with value `east`.
2. **Given** files with strings, numbers, booleans, nulls, lists, and Unicode text, **When** the user imports them, **Then** nested mappings become slash-separated paths, lists remain single values, strings remain text, and other values have a consistent JSON-compatible representation.
3. **Given** an existing head, **When** the user imports with default options, **Then** the new revision remains uncommitted, the head stays unchanged, and the user receives the new revision identifier.
4. **Given** valid inputs, **When** the user requests commit only, **Then** all imported keys are stored before the revision is committed and the existing head stays unchanged.
5. **Given** valid inputs, **When** the user requests head update with or without commit, **Then** the head selects the new revision only after all keys are stored and any requested commit succeeds, subject to existing platform validation.
6. **Given** malformed, unreadable, unsupported, or ambiguous input files, **When** the user imports them, **Then** the operation identifies the invalid input before creating a revision or changing the head.
7. **Given** `robot.yaml` with nested `navigation.speed: {value: 2, metadata: {unit: m/s}}`, **When** the user imports it, **Then** the key `robot/navigation/speed` stores `2` with metadata `{"unit": "m/s"}`, and neither `value` nor `metadata/unit` becomes an additional configuration key.
8. **Given** annotated values containing null, false, zero, empty text, or a list and an empty metadata dictionary, **When** the user imports them, **Then** each wrapped value remains intact and its empty metadata dictionary remains attached to its key.
9. **Given** mappings containing `value` and `metadata` plus another field, or with null/non-dictionary metadata, **When** the user imports them, **Then** those mappings are ordinary configuration data, and ordinary nested mappings are recursively examined for genuine wrappers.
10. **Given** a genuine wrapper whose value is a nested mapping, or a list containing wrapper-shaped mappings, **When** the user imports it, **Then** metadata splitting stops at the genuine wrapper and does not traverse lists; later flattening follows the content rules without inheriting wrapper metadata onto child keys.

---

### User Story 2 - Fast Merge a Referenced Tree Revision (Priority: P1)

As an SDK user, I want to merge compatible configuration from another tree revision into the destination head without prompts so that automated configuration updates are predictable.

**Why this priority**: Merge is the second requested workflow and must be usable in unattended applications.

**Independent Test**: Prepare source and destination trees with disjoint keys and identical shared keys. Merge by source refspec and verify the committed destination revision and new head. Repeat with conflicting shared keys and verify that no destination revision is created.

**Acceptance Scenarios**:

1. **Given** destination keys `a=1` and `shared=2`, and source keys `b=3` and an identical `shared=2`, **When** the user merges, **Then** one new committed destination revision contains all three keys and becomes the destination head; the source revision remains unchanged.
2. **Given** a shared key with different stored data or metadata, **When** the user merges, **Then** the operation fails with the conflicting key names before creating a destination revision, and neither head changes.
3. **Given** each of `org/tree-name`, `org/tree-name/rev-123`, `org/tree-name/release`, `proj/tree-name`, `proj/tree-name/rev-123`, and `proj/tree-name/release`, **When** the user selects a source, **Then** it resolves respectively to the scoped tree's head, explicit revision, or uniquely matching milestone revision.
4. **Given** a source scope different from the destination scope, **When** the user merges, **Then** reads use the source scope and all destination mutations use the destination scope.
5. **Given** an invalid refspec, missing tree or revision, or missing or ambiguous milestone, **When** the user merges, **Then** the operation reports the reference failure before creating a destination revision.
6. **Given** a valid head with no key-value keys, or a source identical to the destination, **When** the user merges, **Then** the operation creates one committed revision with the resulting unchanged or empty key-value set and selects it as head.
7. **Given** a milestone search result containing a revision whose returned labels do not include the exact requested milestone, **When** the user merges, **Then** that revision is not selected, and a missing or ambiguous exact match fails before destination mutation.
8. **Given** a source key whose recorded content length differs from its decoded byte length, **When** the user merges, **Then** the operation identifies that key and fails before creating a destination revision, without changing the source key.

---

### User Story 3 - Edit Pending Revision Keys and Store Them Together (Priority: P1)

As an SDK user, I want to inspect and modify a revision's pending key-value dictionary before it is stored so that I can prepare a complete configuration snapshot and submit it together.

**Why this priority**: An editable dictionary and batch storage are explicitly requested capabilities of the Revision context used by both workflows.

**Independent Test**: Open a revision context, add and replace entries, edit entry metadata, and remove a pending entry through its public dictionary. Verify that successful exit submits exactly the final dictionary in one batch, followed by any requested commit. Repeat asynchronously and with an exception inside the context.

**Acceptance Scenarios**:

1. **Given** an open revision context, **When** the user reads the exposed dictionary repeatedly and adds or replaces an entry through it, **Then** each read exposes the same live pending dictionary and reflects the edits immediately, without writing keys remotely.
2. **Given** pending entries `a`, `b`, and `c`, **When** the user replaces `a`, edits `b`'s metadata, and removes `c`, **Then** successful exit submits exactly the final `a` and `b` entries with their current values and metadata in one batch and makes no per-key write calls.
3. **Given** an empty pending dictionary, **When** the context exits successfully, **Then** it makes zero key-write calls and performs any requested commit according to the normal revision lifecycle.
4. **Given** a pending dictionary containing invalid entry names or payloads, **When** the context exits successfully, **Then** validation fails before any batch write, commit, or head update, and identifies the invalid entry.
5. **Given** pending edits, **When** the context exits with an exception or cancellation, **Then** it submits zero key-write calls and starts no commit or head update.
6. **Given** a successful Import or Merge with several keys, **When** it stores its new revision, **Then** all staged keys use the same editable dictionary and one batch write before commit or head update.
7. **Given** a revision context used directly with commit enabled and no commit message supplied, **When** the context commits, **Then** the revision uses `Created revision through rapyuta-io-sdk-v2` as its message.

---

### User Story 4 - Use Either Execution Mode Reliably (Priority: P2)

As an SDK user, I want the same Import and Merge outcomes in synchronous and asynchronous applications, with clear failures and controlled publication.

**Why this priority**: Equivalent behavior allows users to choose their application's execution model without changing configuration semantics.

**Independent Test**: Run the Import and Merge acceptance scenarios in both execution modes, including failures during storage, commit, and head update; compare keys, metadata, revision status, errors, and head selection.

**Acceptance Scenarios**:

1. **Given** identical inputs and initial tree states, **When** users perform either operation synchronously or asynchronously, **Then** resulting key content, metadata, commit status, head selection, and error conditions are equivalent, apart from generated revision identifiers.
2. **Given** an exception while preparing keys within the revision context, **When** the context exits, **Then** it propagates the exception without storing buffered keys, committing, or updating the head.
3. **Given** a failure while storing keys or committing, **When** either workflow runs, **Then** it propagates that failure, skips subsequent publication steps, and does not request a head update.
4. **Given** successful storage and commit followed by a failed head update, **When** the operation finishes, **Then** it reports failure and makes the created revision identifier available for recovery without reporting publication success.
5. **Given** cancellation of an asynchronous operation during storage, **When** cancellation propagates, **Then** commit and head update are not subsequently started.

### Edge Cases

- No files, empty documents, empty mappings producing no keys, unsupported suffixes, malformed JSON/YAML, multiple YAML documents in one file, and non-mapping document roots are rejected before revision creation.
- JSON and YAML documents are interpreted without executing document-supplied code or constructing arbitrary objects. Import errors identify a file and, when known, a key or location without echoing configuration values or credentials.
- Files in different directories with the same basename stem are rejected, including `robot.json` and `robot.yaml`, even if their document keys differ.
- Literal slash-containing configuration mapping keys, non-string or empty configuration mapping keys, duplicate explicitly authored mapping entries, or other inputs yielding ambiguous flattened paths are rejected rather than silently replacing values. Valid YAML `<<` merges may inherit and explicitly override fields according to YAML precedence. Configuration path components that cannot be encoded as UTF-8, including escaped surrogates, are rejected before revision creation. Extracted metadata names are not configuration paths and may contain slashes.
- `.json`, `.yaml`, and `.yml` are supported; the prefix removes only the final suffix, so `robot.prod.yaml` produces `robot.prod/...`.
- Lists, including empty lists, are leaf values. Empty nested mappings are retained as empty object values. YAML dates are represented as ISO-formatted strings; other non-JSON YAML values are rejected.
- Wrapper detection uses field presence rather than value truthiness: null, false, zero, and empty text are valid wrapped values, and `{}` is valid metadata. A metadata wrapper requires exactly two fields, so extra fields, missing fields, null metadata, and non-dictionary metadata remain ordinary configuration data.
- Extracted metadata is opaque to flattening: its own field names do not become configuration keys. Invalid extracted metadata fails existing key-metadata validation before revision creation; this is separate from deciding whether a wrapper is recognized.
- Splitting examines mapping-valued children of the document, not the document root as a wrapper. Once a wrapper is recognized, its value is not recursively metadata-split. Wrapper-shaped mappings inside lists remain list content.
- A wrapped mapping value is flattened as ordinary content afterward; metadata is associated only with a key at the exact matching path, without inheritance onto descendants. A wrapped empty mapping remains a leaf and retains its metadata.
- Removing or clearing entries in the exposed dictionary inside the context body removes pending writes only; it does not delete inherited keys or mutate an earlier revision. Each revision context has its own dictionary. Behavior of edits through retained references after the body exits, including during finalization, is unspecified.
- Direct edits to encoded key data must keep its checksum and content length consistent; an inconsistent entry is rejected before batch submission with its key identified.
- A selected Merge source key with a content length that differs from its decoded byte length is rejected before destination revision creation, even if the key also exists in the destination. The source payload is neither changed nor normalized.
- Refspecs with missing scope/tree, an unknown scope, an empty selector, or more than three slash-separated components are rejected. A selector starting with `rev-` is always a revision ID.
- A milestone matching multiple revisions is ambiguous even if matches occur on different result pages. The operation must not choose the first match.
- A missing head cannot serve as a merge base or an implicit source revision. An explicit empty key map is allowed; an omitted or null whole key map in either data-included Merge read is an error before revision creation. Missing key data is an error rather than an empty value.
- A tree head cannot be uncommitted under platform rules. If an existing head or selected parent cannot be used for revision inheritance for any other reason, Import or Merge fails explicitly without choosing a fallback parent or advancing the head.
- Shared keys with identical data but different metadata conflict. Absent metadata and empty metadata are distinct, matching rio's comparison behavior.
- Empty text, null, false, and zero are real values and must not be mistaken for absent keys.
- Source and destination may be the same tree. The selected source revision remains unchanged while the destination receives a new revision and advances its head.
- If the destination head changes after Merge reads it, Merge still uses the originally read head as its parent and may select its new revision as head; it does not re-read or retry automatically.
- Failures may leave an uncommitted or committed new revision. Automatic deletion or rollback of remotely completed operations is outside scope; failed workflows never deliberately advance the head afterward.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST have synchronous and asynchronous Import and Merge workflows with equivalent inputs, outcomes, and failure semantics.
- **FR-002**: Import MUST accept one or more named local JSON/YAML files, including a mixture of supported formats, targeting an existing Configtree in a selected organization or project scope.
- **FR-003**: Import MUST safely parse and validate all documents, without executing document-supplied code or constructing arbitrary objects, and detect prefix/path ambiguity before creating a revision. Invalid input MUST identify the affected file and, when known, key or location without including configuration values or credentials in error details.
- **FR-004**: Import MUST split key content from metadata using the rio rules below before flattening nested content mappings into slash-separated keys prefixed by the filename stem. It MUST combine all documents into one key space and follow the leaf-value rules in Edge Cases.
- **FR-005**: Import MUST create exactly one fresh revision for each successful invocation and store all imported keys in that revision. It MUST NOT reuse CLI state or a prior uncommitted revision. If the existing head cannot serve as the normal inherited parent, Import MUST fail rather than select a fallback parent.
- **FR-006**: Import MUST expose independent commit and head-update choices, both disabled by default. Storage MUST precede commit, and head update MUST follow successful storage and any requested commit.
- **FR-007**: Each successful workflow MUST return the created revision identifier. If a later step fails after creation, the failure MUST make that identifier available alongside the failed stage. Cancellation MUST retain its normal cancellation semantics while making an already known revision identifier recoverable.
- **FR-008**: Refspec parsing MUST produce four components: organization-scope flag (`true` for `org`, `false` for `proj`), tree name, optional revision ID, and optional milestone. The selector fields MUST be mutually exclusive and both absent when the selector is omitted.
- **FR-009**: Refspec parsing MUST accept exactly `org/<tree>[/<selector>]` or `proj/<tree>[/<selector>]`, with nonempty components. A selector beginning with `rev-` MUST populate revision ID; any other valid selector MUST populate milestone.
- **FR-010**: Merge MUST resolve an omitted selector to the source head, an explicit revision ID to that revision, and a milestone to exactly one revision bearing the exact requested `rapyuta.io/milestone` label. It MUST check the labels on returned revisions rather than relying only on the search filter. Zero or multiple exact matches MUST fail before destination mutation, considering all result pages.
- **FR-011**: Merge MUST use the destination head read at the start of the operation as its pinned base and require valid source and destination revisions with non-null key maps from data-included reads. An explicit empty map is valid; an omitted or null map MUST fail before creating a revision. It MUST preserve independent source and destination scopes. If that base cannot serve as a parent, Merge MUST fail rather than select a fallback parent. It MUST NOT re-read or retry automatically if another writer changes that head before publication.
- **FR-012**: Fast merge MUST retain destination-only keys and add source-only keys. A shared key is compatible only when its stored data and metadata are equal; any incompatible shared key MUST fail the whole merge with the conflicting key names before creating a revision.
- **FR-013**: Successful Merge MUST create one fresh destination revision, store the complete merged key-value set, commit it, and then set it as destination head. It MUST NOT mutate the selected source revision or advance a different source tree's head.
- **FR-014**: Both workflows MUST operate on key-value configuration content. Import MUST store strings as text and non-string leaf values in a JSON-compatible form; Merge MUST retain the stored data and metadata of selected key-value entries without lossy re-serialization. Before destination revision creation, Merge MUST reject every selected source key whose recorded content length is absent or differs from its decoded byte length, identify the affected key, and leave the source payload unchanged.
- **FR-015**: Merge MUST NOT prompt, launch an editor, skip conflicting keys, or apply a partial merge. A failed compatibility check MUST leave both trees unchanged.
- **FR-016**: Both workflows MUST propagate input, resolution, authorization, storage, commit, and head-update failures. They MUST stop before starting later workflow stages after failure or asynchronous cancellation, and MUST NOT report success for an incomplete operation.
- **FR-017**: The revision context MUST expose its live pending key-value dictionary and finalize its validated contents using one batch write only on successful exit. A submitted batch MUST return `success=true` with no nonempty error before an optional commit or head selection; absent, null, or false success MUST stop publication. It MUST propagate exceptions without finalizing buffered work on unsuccessful exit. When used directly with commit enabled and no message supplied, it MUST use `Created revision through rapyuta-io-sdk-v2` as the commit message.
- **FR-018**: The asynchronous workflow MUST use asynchronous platform operations and preserve cancellation propagation. Both modes MUST use the caller's client configuration and MUST NOT depend on CLI prompts, state files, spinners, or process exits.
- **FR-019**: Scope MUST be limited to Import with rio-compatible metadata splitting, non-interactive fast Merge, refspec resolution, and revision lifecycle support including an editable pending dictionary and batch storage. Export, overrides, ETCD integration, interactive or three-way merge, file upload, remote key rename/delete helpers, and a complete CLI port are excluded.
- **FR-020**: Import MUST recognize a mapping-valued child as a metadata wrapper if and only if it contains exactly `value` and `metadata` and `metadata` is a dictionary, including an empty dictionary. It MUST extract the value and attach the dictionary as metadata at that same path, without flattening the extracted metadata itself.
- **FR-021**: Import MUST recursively split ordinary mapping-valued children that do not satisfy FR-020 and preserve non-mapping values unchanged. It MUST stop splitting within a recognized wrapper's value and MUST NOT search inside list elements or treat the document root as a wrapper.
- **FR-022**: After splitting, Import MUST flatten the content and metadata paths separately, preserving each extracted metadata dictionary as an indivisible attachment. A resulting content key MUST receive metadata only from an exact matching prefixed path; metadata MUST NOT be inherited or copied to descendant keys. Extracted metadata MUST satisfy the existing key-metadata contract before remote mutation.
- **FR-023**: Each revision context MUST publicly expose the same live dictionary of pending key-value entries throughout its context body. Users MUST be able to add, replace, and remove entries and edit entry metadata in that dictionary while the body is active. These edits MUST alter the eventual batch contents without causing immediate remote writes, and separate contexts MUST NOT share their pending dictionaries. The workflow MUST NOT add a special mechanism to prevent edits through retained references after the body exits; the behavior of such edits is unspecified.
- **FR-024**: A nonempty pending dictionary MUST be validated and submitted in exactly one batch key-write operation on successful context exit. An empty dictionary MUST produce zero key-write operations. Neither case MUST use per-key writes, and Import and Merge MUST use this same behavior. Revision initialization, optional commit, and head update remain separate platform operations.
- **FR-025**: Before batch submission, the revision context MUST validate the final edited entry names and payloads against the existing key-value contracts, plus helper-specific storage prerequisites: nonempty key names, present and decodable encoded data, required key-value content type, checksum and content length, and agreement of those derived fields with the encoded bytes. Inconsistent direct edits MUST fail with the affected key identified, without submitting keys or starting commit/head update. These helper checks MUST NOT tighten the existing low-level model contracts. Removing a pending entry MUST NOT request deletion of a remotely stored or inherited key.

### Metadata Splitting Rules

The rio behavior applies to each mapping-valued child while traversing the document's configuration mappings. A genuine wrapper is replaced by its `value` in the content tree, and its `metadata` is kept separately at the same path. Ordinary mappings are traversed recursively; scalars and lists are retained without traversal. A recognized wrapper's value is passed through without further metadata splitting. Extracted metadata stays opaque during subsequent path flattening.

For a file named `robot.yaml`, these examples define observable results:

| Document entry | Imported content | Attached metadata |
| --- | --- | --- |
| `speed: {value: 2, metadata: {unit: m/s}}` | `robot/speed = 2` | `robot/speed` receives `{unit: m/s}` |
| `enabled: {value: false, metadata: {}}` | `robot/enabled = false` | `robot/enabled` receives `{}` |
| `limit: {value: null, metadata: {source: defaults}}` | `robot/limit = null` | `robot/limit` receives `{source: defaults}` |
| `speed: {value: 2, metadata: null}` | `robot/speed/value = 2`, `robot/speed/metadata = null` | None |
| `speed: {value: 2, metadata: {unit: m/s}, note: tuned}` | `robot/speed/value = 2`, `robot/speed/metadata/unit = m/s`, `robot/speed/note = tuned` | None |
| `group: {value: {speed: 2}, metadata: {unit: m/s}}` | `robot/group/speed = 2` | None at the child path; group metadata is not inherited |

### Required SDK Compatibility and Constitution Constraints

These are integration constraints explicitly requested by the user or required by the project constitution; detailed helper signatures and internal design belong in the implementation plan.

- Synchronous orchestration MUST use `Client`; asynchronous orchestration MUST use `AsyncClient`. Both MUST use a Revision context manager with the corresponding execution mode.
- Higher-level workflows and revision context support MUST reside in separate helper modules outside the client implementation modules. Existing client methods MUST remain one-to-one platform operations.
- Affected public operations are `get_configtree`, `list_revisions`, `create_revision`, `put_keys_in_revision`, `commit_revision`, and `set_configtree_revision`, and their asynchronous counterparts. No additional platform operation is required by this scope.
- Affected request/response contracts are `ConfigTree`, `ConfigTreeRevision`, `ConfigTreeRevisionMetadata`, `ConfigTreeRevisionList`, `ConfigValues`, `ConfigValue`, `BaseMetadata`, and `APIResponse`. Existing typed payload validation, serialization aliases, and omitted-field behavior MUST be preserved.
- The exposed dictionary MUST hold entries compatible with `ConfigValue`, and the final dictionary MUST be validated through `ConfigValues` before batch submission with `put_keys_in_revision` or its asynchronous counterpart. Mutable dictionary access MUST NOT bypass typed request validation.
- New public helpers MUST document typed inputs, outputs, and failures, retain the declared package compatibility, and satisfy the constitution's lint and formatting gates. This specification proposes no constitution exceptions.

### Key Entities *(include if feature involves data)*

- **Configuration document**: One named JSON/YAML file with a mapping root; its filename stem supplies the key prefix.
- **Flattened key-value entry**: A slash-separated name, stored value, and optional metadata within a Configtree revision.
- **Metadata wrapper**: A configuration mapping with exactly `value` and dictionary-valued `metadata`, split into ordinary content and an opaque metadata attachment at the same path.
- **Pending key-value dictionary**: The publicly editable collection of key entries belonging to one active revision context; its final validated state supplies a single batch write.
- **Scoped Configtree**: A named organization or project configuration tree with a selected head revision.
- **Revision**: A configuration snapshot identified within its tree, with a commit status and an optional relationship to an existing head.
- **Refspec**: A source reference comprising scope, tree name, and either no selector, a revision ID, or a milestone.
- **Milestone**: A revision label used to select exactly one revision within a scoped tree.
- **Merge conflict**: A shared key whose data or metadata differ between the source revision and destination head.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can import at least three documents spanning JSON, YAML, and YML in one invocation, obtaining exactly one new revision with 100% of expected prefixed keys and no lost leaf values.
- **SC-002**: All four combinations of Import commit/head-update choices yield the specified revision status and head-update behavior in both execution modes, including reporting any platform rejection of an uncommitted head.
- **SC-003**: All six refspec forms resolve to the correct scoped source; every missing or ambiguous reference in the acceptance matrix fails without destination mutation.
- **SC-004**: Every compatible merge in the acceptance matrix retains 100% of destination-only keys, adds 100% of source-only keys, and publishes one committed revision without user intervention.
- **SC-005**: Every conflicting merge in the acceptance matrix reports the conflicting keys, creates zero destination revisions, and leaves both heads unchanged.
- **SC-006**: Synchronous and asynchronous runs agree on 100% of specified acceptance outcomes, excluding generated identifiers. All injected failures prevent subsequent publication stages and expose recovery information when a revision identifier is already known.
- **SC-007**: SDK users can complete Import and Merge through a single documented workflow invocation per operation without managing individual key writes or answering prompts.
- **SC-008**: All metadata examples and boundary cases produce the specified content paths and exact metadata attachments in both execution modes, with zero configuration keys generated from extracted metadata fields.
- **SC-009**: In both execution modes, all valid pending-dictionary edits are reflected in the stored batch: added and replaced entries use their final contents, edited metadata is retained, and removed pending entries are absent.
- **SC-010**: Each valid nonempty revision context reaching submission attempts exactly one batch of keys regardless of the number of pending entries; empty contexts and contexts aborted by body exceptions, cancellation before submission, or validation failures submit zero key-write operations. Import and Merge make zero per-key write calls.

## Assumptions

- Users supply an authenticated client, existing target trees, and permission to read the source and mutate the destination; project scope is the default when no target scope is explicitly selected.
- Documents are local UTF-8 files with mapping roots; one file contains one document. Raw text inputs and unnamed in-memory documents are outside the initial scope because prefixing depends on filenames.
- Slash separators, the `rev-` revision-ID convention, milestone labels, data/metadata conflict checks, and Merge's automatic commit/head update follow the installed rio CLI behavior inspected for this specification. Filename/path ambiguity is rejected explicitly for deterministic SDK behavior.
- Metadata splitting follows the installed rio CLI's `split_metadata` recognition and traversal rules, including empty metadata and no recursive splitting of a recognized wrapper's value. Existing SDK key metadata accepts string names and string values; unsupported metadata is reported rather than silently converted or discarded.
- The publicly editable dictionary is the context's staged key-entry collection, including value payloads and metadata. This request does not introduce a separate raw-content dictionary or remote deletion semantics. Batch storage means one key-write operation after revision initialization, using the final staged contents on successful exit.
- Import's commit and head-update choices are independent, following rio behavior. Selecting an uncommitted revision as head remains subject to the platform's existing validation; a platform rejection is reported with the new revision identifier.
- New Import revisions retain the platform's normal parent/inheritance behavior. The platform does not allow an uncommitted revision as tree head; any other unusable existing parent causes explicit failure. Imported paths are written with their supplied values; this feature does not introduce replacement of unrelated existing keys or key deletion.
- Fast merge concerns key compatibility, not revision ancestry. It does not need common-ancestor or historical-milestone analysis. Source-only binary/file content is outside scope; unrelated content inherited by the platform is not actively deleted.
- Head selection has no atomic comparison with the previously read head. Concurrent writers can change the destination head during Merge, so callers requiring strict ordering serialize those writes.
- Remote operations are not assumed to be transactional. A failed or cancelled request may have completed remotely; the workflow reports uncertainty and does not attempt automatic rollback or retry of mutations. If creation completes remotely without returning its identifier, recovery cannot promise that identifier.
- No Revision context manager currently exists in this SDK. Providing the minimum synchronous/asynchronous lifecycle support for these workflows is part of the feature, without porting the CLI's broader revision helpers.
