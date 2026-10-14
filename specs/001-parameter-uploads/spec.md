# Feature Specification: Parameter Uploads

**Feature Branch**: `chore/bootstrap-spec-kit`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "Implement support for Parameter uploads. For this add support for v1 Parameter APIs in the Client and AsyncClient. Then build a high-level Helpers for submitting the full directories with files. Use the CLI and SDK v1 as the reference for the implementation."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage individual Parameter resources (Priority: P1)

As a platform integrator, I can manage existing v1 Parameter trees and individual nodes through either `Client` or `AsyncClient`, so I can build workflows without relying on the older SDK.

**Why this priority**: Individual operations provide useful configuration management on their own and form the foundation for directory submissions.

**Independent Test**: In one project, list trees, create a tree and its child nodes, read the hierarchy, obtain its blob references, and delete the tree. Repeat using both clients and compare the visible results.

**Acceptance Scenarios**:

1. **Given** a project with existing trees, **When** the user lists trees and reads a complete tree, **Then** its recursive nodes expose names, types, hierarchy, inline content, and available blob references matching the platform's stored resources.
2. **Given** a valid project and path, **When** the user creates or updates a value, attribute, folder, or inline file node, **Then** that node has the supplied type and content under the requested path.
3. **Given** a binary file requiring upload, **When** the user requests upload authorization and later confirms a completed transfer, **Then** authorization and completion results are exposed as separate operations.
4. **Given** an existing tree or node and any required node version, **When** the user deletes it, **Then** unrelated resources remain available and the platform's deletion result is returned; deleting an absent resource preserves the platform's idempotent behavior.
5. **Given** equivalent inputs and platform responses, **When** either client performs any supported operation, **Then** both expose equivalent validated results and failures.
6. **Given** invalid credentials, insufficient permissions, a missing resource, or malformed returned data, **When** an operation is attempted, **Then** the user receives a failure that distinguishes the cause and no fabricated success.

---

### User Story 2 - Submit complete directory trees (Priority: P1)

As a developer maintaining configuration files locally, I can submit a directory containing one or more Parameter trees through a synchronous or asynchronous helper, so I do not have to create each folder and upload each file manually.

**Why this priority**: Directory submission is the primary requested workflow and removes repetitive work for configuration owners.

**Independent Test**: Submit two trees containing nested and empty folders, YAML, JSON, arbitrary text, binary files, and large files. Inspect the stored hierarchy and retrieve files using existing reference tooling.

**Acceptance Scenarios**:

1. **Given** a source containing `config/` and `secrets/`, **When** submitted without a filter, **Then** both immediate child directories become trees and their nested folders and files retain their relative paths; loose files beside those trees are ignored.
2. **Given** the same source, **When** only `config` is selected, **Then** only that tree is submitted and `secrets` is untouched.
3. **Given** files at several nesting levels and empty folders, **When** submitted in default folder mode, **Then** every regular file and folder beneath selected trees is represented, including empty folders.
4. **Given** small valid YAML and JSON files, **When** submitted, **Then** their original text and content types are preserved as inline files; inline YAML must contain a mapping and inline JSON must contain valid JSON, consistent with SDK v1.
5. **Given** arbitrary text, binary content, a file exceeding the inline limit, or a small structured file whose stored representation exceeds that limit, **When** submitted, **Then** its original bytes are uploaded through blob storage and become available at the intended path.
6. **Given** an authorized binary transfer, **When** transfer fails, **Then** completion is not confirmed; when transfer succeeds, submission is successful only after confirmation succeeds.
7. **Given** content already present remotely, including identical content shared by multiple files, **When** the platform confirms that no transfer or further confirmation is needed, **Then** all intended paths are represented without a false failure.
8. **Given** invalid source arguments or invalid inline structured content, **When** submitted, **Then** the helper identifies the offending source or file and reports failure.
9. **Given** an empty source, a partially matching filter, or skipped filesystem entries, **When** submitted, **Then** the outcome records zero uploaded trees for the empty source and identifies unmatched names and skipped entries without hiding completed uploads.
10. **Given** a submission with multiple large files, **When** uploaded asynchronously, **Then** unrelated asynchronous work can continue and processing does not require loading all selected file contents simultaneously.
11. **Given** completed files and skipped entries before asynchronous cancellation, **When** the caller awaits the cancelled submission, **Then** cancellation remains observable as cancellation and its exception exposes the failing path/stage and an immutable partial outcome identifying known completed trees/files, deleted trees, created directories, and skipped entries; unfinished content is not reported complete.
12. **Given** an eligible blob file of at most 209715200000 bytes or one byte above that limit, **When** preflight runs, **Then** the boundary file passes the size check and the oversized file fails with its path before tree deletion, creation, or upload.
13. **Given** malformed `.yaml` or `.json` content with raw size at most 131072 bytes whose escaped representation would exceed the inline limit, **When** submitted, **Then** validation fails before the serialized-size decision; the same malformed content routed directly to a blob by exceeding the raw-size threshold is transferred unchanged.

---

### User Story 3 - Control replacement and legacy compatibility (Priority: P2)

As a configuration owner, I can choose whether to recreate selected trees and whether to use SDK v1's legacy value/attribute hierarchy, so uploads fit existing configuration consumers.

**Why this priority**: Existing projects need predictable replacement behavior and compatibility with previously published hierarchies.

**Independent Test**: Upload over an existing tree with replacement disabled and enabled, then submit a legacy hierarchy fixture and inspect node types and file placement.

**Acceptance Scenarios**:

1. **Given** an existing selected tree with a remote-only file, **When** replacement is disabled, **Then** no tree deletion is initiated and existing content is handled according to the platform's individual update semantics, with conflicts reported.
2. **Given** the same tree, **When** replacement is enabled, **Then** the selected tree is deleted and recreated from the source, removing remote-only content while leaving unselected trees unchanged.
3. **Given** a selected tree absent from the project, **When** replacement is enabled, **Then** absence does not prevent creation of that tree.
4. **Given** a directory intended for legacy mode, **When** that mode is explicitly selected, **Then** the root is a value node, child directory levels alternate attribute and value nodes, and files directly inside attribute directories are ignored as in SDK v1.
5. **Given** several selected files and failure after some uploads complete, **When** submission ends, **Then** it identifies the failed path and stage, does not claim whole-submission success, and states that remote changes may already exist.

### Edge Cases

- An absent, unreadable, or non-directory source fails with source context before tree deletion or creation begins.
- A source with no child directories, including one containing only loose files, completes as an explicit no-op with zero uploaded trees.
- An omitted or empty filter selects all immediate child directories. A non-empty filter selects exact names; if none match, submission fails before remote changes. If only some match, matching trees are submitted and unmatched names are reported as skipped.
- Tree names follow the CLI's actual validator: 1–50 characters, starting with an ASCII letter or digit, followed by ASCII letters, digits, periods, underscores, or hyphens. Invalid selected names fail before remote changes.
- Duplicate filenames in different folders retain distinct paths. Names are addressed literally without renaming; names unsupported by the platform, including spaces or reserved characters, produce an attributable validation failure.
- Symbolic links and non-regular filesystem entries are skipped and reported, preventing cycles or traversal outside selected sources. Hidden regular files and directories remain eligible.
- Zero-byte ordinary files are uploaded unchanged; empty inline YAML is invalid because it is not a mapping, and empty inline JSON is invalid JSON.
- The 128 KiB inline limit includes the stored representation and the reference's metadata allowance, not only source file size. Boundary files must use the reference's size decision without content loss or duplicate uploads. Each eligible blob file may contain at most 209715200000 bytes; a larger file fails local preflight before any remote mutation, identifying its path and the supported limit.
- Files routed directly to blob storage because their raw size exceeds 131072 bytes or their extension is neither `.yaml` nor `.json` preserve bytes without YAML/JSON parsing. Files with either structured extension and raw size at most 131072 bytes are decoded and validated before the serialized-size decision, even if that later decision routes them to blob storage. Malformed structured candidates fail with their path, consistent with SDK v1.
- A file removed or changed during submission, interrupted transfer, expired authorization, or failed confirmation produces an attributable failure and no whole-submission success.
- Only explicit platform confirmation of already-uploaded content counts as success; incomplete authorization must not silently discard a file.
- Replacement or upload failure may leave a partially changed tree. Automatic rollback and atomic multi-tree submission are outside scope.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Both `Client` and `AsyncClient` MUST support the following v1 Parameter operations with equivalent inputs, validated output contracts, and failures. Each client method MUST represent one platform operation.

  | Operation | Input contract | Output contract |
  | --- | --- | --- |
  | List Parameter trees | Project context | Tree names |
  | Read a complete tree | Project context and tree name | Recursive node with type, name, children, inline content, and blob reference when present |
  | Create or update a node | Path and node description: value, attribute, folder, or inline file with content type and original text | Platform mutation acknowledgment |
  | Delete a tree or node | Project context and path; child-node deletion includes its version and applicable node metadata | Platform deletion acknowledgment |
  | List tree blob references | Project context and selected tree names | Blob references with identifiers and available download authorizations |
  | Prepare binary upload | Path, node version, checksum, content type, and optional content encoding | Blob identifier and upload authorization, or confirmation that content is already uploaded |
  | Confirm binary upload | Project context, tree name, and blob identifier | Platform completion acknowledgment |

- **FR-002**: Parameter operations MUST use the configured environment and project, allow the v1 service location to be overridden, and honor existing authentication and per-call context conventions. Selecting a v1 service location MUST preserve existing resource behavior.
- **FR-003**: Public Parameter payloads MUST have validated, named model contracts for tree lists, recursive nodes, node submissions, mutation acknowledgments, blob reference lists, upload authorizations, and completion results. Contracts MUST preserve v1 field meanings and distinguish omitted from explicit values; operations without payloads MUST document that absence.
- **FR-004**: Directory upload MUST be available through separate synchronous and asynchronous helpers composing public client operations. Authentication, environment, and project MUST come from the supplied client.
- **FR-005**: Helpers MUST treat the supplied directory as a container of trees, select immediate child directories using the documented exact-name filter, and ignore loose files in that container.
- **FR-006**: Folder mode MUST be the default and preserve every eligible nested regular file, empty folder, filename, and relative path. Tree roots MUST retain the reference's value-node semantics; descendant directories MUST be folder nodes.
- **FR-007**: An explicit legacy hierarchy mode MUST reproduce the reference's alternating value/attribute directory semantics and ignored attribute-level files.
- **FR-008**: Helpers MUST preserve original YAML/JSON text and follow SDK v1's classification order: route files above the 131072-byte raw-size threshold and other extensions directly to blobs; decode and validate `.yaml`/`.json` candidates at or below that threshold before checking the stored representation plus metadata allowance against 128 KiB. Candidates that subsequently exceed the stored-size limit MUST use blobs, while malformed candidates MUST fail. Classification MUST run once per eligible file in either hierarchy mode.
- **FR-009**: Binary submissions MUST preserve bytes, supply the reference's integrity and file metadata, transfer only when authorization requires it, and confirm completion only after successful transfer. Platform credentials MUST remain confined to platform operations rather than being attached to external storage transfers.
- **FR-010**: Helpers MUST accept confirmed already-uploaded content as success, including the reference's duplicate-content completion cases, without accepting unrelated errors or incomplete authorizations as success.
- **FR-011**: Helpers MUST default to preserving existing trees without initiating deletion. Explicit recreation MUST delete and recreate only selected trees, tolerate absent trees according to platform semantics, and stop processing a tree if its deletion fails.
- **FR-012**: Helpers MUST validate source existence, directory readability, selected tree names, option values, and the 209715200000-byte maximum for each eligible blob file before remote mutations. An oversized file MUST fail with its path and the supported limit. Empty selections and unmatched names MUST follow the edge-case rules.
- **FR-013**: Helpers MUST skip and report symbolic links and non-regular entries, retain eligible hidden entries, and keep submitted paths inside their selected tree.
- **FR-014**: Each submission MUST have an inspectable outcome identifying completed trees/files and skipped entries. Failures MUST identify the affected local or Parameter path, failing stage, and known partial completion, while preserving the underlying error. Asynchronous cancellation MUST preserve cancellation semantics and expose the same structured failure context and immutable partial outcome as ordinary failures, rather than only completion counts.
- **FR-015**: Whole-submission success MUST require all selected eligible content to be available and every required binary completion confirmed. Helpers MUST NOT require all selected file contents to be loaded simultaneously; asynchronous network transfers MUST allow other asynchronous work to continue.
- **FR-016**: Public documentation MUST include runnable synchronous and asynchronous examples for upload, tree selection, recreation, legacy mode, and error handling, stating default and partial-failure behavior.
- **FR-017**: The feature MUST preserve existing v2 ConfigTree workflows and allow uploaded Parameter trees to be listed, read, and downloaded using the existing CLI and SDK v1. Acceptance MUST include a required network-isolated round-trip using the reference SDK's actual public downloader, which the reference CLI delegates to, against captured results of both upload helpers. Missing reference tooling, skipped cases, or recording unavailable live credentials MUST NOT substitute for that compatibility check. Supplemental live validation MUST be reported separately.

### Key Entities *(include if feature involves data)*

- **Parameter Tree**: Project-scoped named root containing nodes, independently selected or recreated during submission.
- **Parameter Node**: Named item at a tree-relative path, typed as a value, attribute, folder, or file, with children, inline text, or a blob reference as applicable.
- **Local Submission Source**: Container directory and selected immediate child directories, with eligible files, folders, hierarchy mode, and recreation choice.
- **Blob Reference and Authorization**: Identity of binary content, checksum and media metadata, and temporary upload/download authority. Transfer and confirmed availability are distinct states.
- **Submission Outcome**: Completed trees/files and skipped entries, or a failure containing path, stage, underlying cause, and known partial completion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can submit two trees containing at least 100 mixed files across five directory levels with one helper invocation, with 100% of eligible paths and contents preserved and no manual per-file work.
- **SC-002**: All seven individual operation categories and acceptance scenarios applicable to both client modes produce equivalent visible outcomes in synchronous and asynchronous use. Asynchronous responsiveness and cancellation scenarios are verified separately against their stated acceptance criteria.
- **SC-003**: For filtered and recreation scenarios, 100% of selected trees follow requested behavior and zero unselected trees are modified.
- **SC-004**: Folder and legacy fixtures produced by both upload helpers are reconstructed by the actual reference SDK downloader in a network-isolated compatibility run with zero skipped cases; 100% of eligible paths and empty folders match, inline files preserve original text, and blob files match original byte checksums, including size-boundary and duplicate-content cases. A live check is supplemental evidence, not a substitute for the required isolated run.
- **SC-005**: Every injected validation, transfer, and completion failure identifies the affected path and stage, and zero incomplete submissions are reported as complete.
- **SC-006**: A user following each documented upload example can complete the workflow without consulting older SDK internals or writing traversal and transfer logic.

## Assumptions

- This invocation produces the feature specification; implementation design and executable tasks follow in planning.
- Users already have credentials, a project, and Parameter management permissions. Existing v1 Parameter and authorized blob storage services are dependencies.
- "v1 Parameter APIs" means the operation set used by CLI and SDK v1 Parameter workflows, including read/delete and blob-reference discovery. Device apply operations, high-level download/diff helpers, ConfigTree migration, a new CLI command, automatic retry/resume, and atomic rollback are outside scope.
- Folder mode defaults to the CLI behavior because the requested helper submits full directories with files. SDK v1 legacy mode remains an explicit option rather than its default.
- For selection, empty sources, tree-name validation, and legacy file placement, actual reference behavior takes precedence over inconsistent reference prose. Partial selection matches are reported, following CLI selection behavior.
- YAML mapping validation and JSON syntax validation apply to `.yaml`/`.json` candidates with raw size at most 131072 bytes, before the stored-size decision, as in SDK v1. Other extensions and structured files above the raw-size threshold bypass parsing and use blob storage. The helper's 209715200000-byte maximum is a documented SDK constraint, not a platform-wide maximum.
- Sources are expected to remain stable during submission. Concurrent changes are reported when detected; local snapshots are outside scope.
- Planning verified the server routes: child nodes are read within a complete tree, not through a separate child GET operation. Node mutations preserve optimistic version semantics; a helper creating an existing tree without recreation may fail as in SDK v1. These details refine the operation contracts without adding a new workflow.
- Constitution 1.0.0 governs planning and implementation, including equivalent client contracts, validated payload models, separate workflow helpers, and repository quality checks. The operation and entity lists identify affected public contracts; internal design belongs in the plan.
- Reference evidence: [CLI Parameter documentation](https://cli.rapyuta.io/parameter.html) and [SDK v1 Parameter documentation](https://sdk.rapyuta.io/parameter.html). Sources inspected: `/home/ankit/Projects/Work/rapyuta-io-cli` revision `27bb77bb912705b58a5de0a2e99848dc023ba322` (`riocli/parameter/upload.py`, `riocli/parameter/utils.py`, Parameter tests) and `/home/ankit/Projects/Work/rapyuta-io-sdk` revision `739a6fe44600ff0964fa56b04878ddb21e76b5be` (`rapyuta_io/clients/paramserver.py`, parsing utilities, Parameter tests). These reference source files had no pending modifications when inspected.
