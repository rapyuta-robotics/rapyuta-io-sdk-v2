# Feature Specification: Chart Support

**Feature Branch**: `feat/charts`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "Implement the Chart support as a wrapper of the existing Applier / Async Applier classes. The chart is a mechanism to package templates and default values. See the reference implementation in the rio CLI."

## Clarifications

### Session 2026-10-13

- Q: May the standard repository index URL be a fixed constant? → A: Yes. The reference index URL will not change and may be hard-coded as a constant.
- Q: Is branch-specific repository URL construction part of this feature? → A: Yes. Include the CLI branch repository base, path construction, and URL-encoding behavior in scope.
- Q: What is the compatibility baseline for Chart behavior? → A: The implementation must have parity with the rio CLI Chart implementation, including repository entry selection, package URL selection, defaults, branch handling, and recreation, while composing the existing SDK Applier contracts.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Use a packaged application from a synchronous program (Priority: P1)

An SDK user selects a chart containing application templates and default values, supplies any application-specific values and secrets, and applies or deletes its resources using their configured client. The user receives the same resource outcomes they would receive from applying those templates directly.

**Why this priority**: Packaging existing templates and delegating their lifecycle is the core purpose of Chart support.

**Independent Test**: Load a local chart with two related resources, apply it with controlled platform responses, and delete it. Compare its rendered resources, operation order, and outcomes with direct Apply use on the same template files and effective values.

**Acceptance Scenarios**:

1. **Given** a chart with valid metadata, templates, and bundled values, **When** the user applies it without supplying values, **Then** all supported template files are rendered using the bundled values and its resources follow the existing Apply dependency and readiness rules.
2. **Given** the same chart and an explicit values source, **When** the user prepares it, **Then** that source replaces the bundled defaults as the values input, matching the CLI; a missing required value fails rather than falling back to bundled values.
3. **Given** two ordered explicit values sources with overlapping nested keys, **When** the chart is prepared, **Then** they merge under the existing Apply rules, with later values taking precedence, mappings merging recursively, and lists and scalar values replacing earlier ones.
4. **Given** supplied secrets, explicit platform template context, and any required device-interface information, **When** chart templates render, **Then** those inputs have the same meaning and reserved namespaces as in direct Apply use.
5. **Given** chart resources with dependencies, a retained resource, and an already absent resource, **When** deletion runs, **Then** dependents precede prerequisites, retained resources receive no deletion request, and absence is a successful outcome.
6. **Given** a caller-owned client and input mappings, **When** apply or delete succeeds or fails, **Then** the client remains usable, its configuration and the input mappings remain unchanged, and the operation exposes the existing Apply result and failure information.
7. **Given** a chart apply request with recreation enabled, **When** it runs, **Then** a delete phase using the same rendered inputs finishes successfully before a fresh apply phase begins; if deletion fails or is cancelled, apply does not begin. In preview mode both phases are planned without platform requests.

---

### User Story 2 - Use the same chart in an asynchronous application (Priority: P1)

An SDK user loads and manages a chart while other asynchronous application work continues. The chart accepts the same inputs and provides the same lifecycle behavior as synchronous use.

**Why this priority**: Wrapping both existing Applier variants is an explicit requirement, and asynchronous users need the complete chart workflow.

**Independent Test**: Prepare and apply a chart with controlled delayed acquisition and resource responses while an unrelated task runs. Compare the resources and outcomes with synchronous use and cancel a separate run during acquisition and another during execution.

**Acceptance Scenarios**:

1. **Given** equivalent chart contents, inputs, settings, and platform responses, **When** users apply, delete, inspect, or preview through either execution mode, **Then** resolved resources, intended actions, and outcome categories agree.
2. **Given** delayed chart retrieval or resource operations, **When** asynchronous use runs, **Then** unrelated application work continues, and resource execution honors the existing worker and readiness settings.
3. **Given** cancellation during chart retrieval or resource execution, **When** cancellation returns to the caller, **Then** owned temporary artifacts are released, no background chart retrieval or resource requests continue, and any completed resource work remains inspectable under the existing Apply cancellation contract.
4. **Given** a prepared chart, **When** the user previews repeatedly and then applies or deletes it sequentially with different compatible clients, **Then** every execution uses its supplied client's scope and fresh operation state, without carrying server-derived identities across calls.

---

### User Story 3 - Obtain a published chart by name and version (Priority: P2)

An SDK user selects a published chart from the standard chart repository, a branch preview repository, or a caller-selected repository without manually downloading and unpacking its templates. Users can also use a local chart directory or packaged archive for offline and private workflows.

**Why this priority**: Repository retrieval is the CLI's chart distribution mechanism and makes existing published applications reusable through the SDK.

**Independent Test**: Serve a controlled repository index and packaged chart. Select an exact version, retrieve it, and compare its prepared resources with the equivalent local directory and local archive, without contacting a live platform.

**Acceptance Scenarios**:

1. **Given** a repository index with multiple versions of a chart, **When** the user requests `name:version`, **Then** the exact matching version is loaded and its name and version are available for inspection.
2. **Given** matching repository entries and no version specified, **When** the user selects the chart by name, **Then** the first entry in repository order is loaded, matching the CLI; if several entries match, the user receives a non-fatal diagnostic advising explicit version selection and loading continues.
3. **Given** an unknown chart, missing version, failed download, malformed index, or invalid archive, **When** retrieval runs, **Then** an actionable error identifies the chart or source and failed stage, no platform mutation begins, and owned temporary artifacts are released.
4. **Given** equivalent chart contents supplied as a directory, local archive, and repository package, **When** each is prepared with the same inputs, **Then** each produces the same resource documents and deterministic input order.
5. **Given** an archive entry that would escape the extraction area or link to an external file, **When** the package is loaded, **Then** it is rejected before external files are read or changed.
6. **Given** a branch name, **When** its repository URL is constructed, **Then** the result uses the CLI branch base followed by the encoded branch path and `/incubator/index.yaml`; `/` within the branch is preserved, while spaces, `?`, and non-ASCII characters are encoded.
7. **Given** a branch preview selection, **When** chart lookup, metadata inspection, or loading runs, **Then** it uses the branch-specific index; with no branch or an empty branch, it uses the supplied repository override or the fixed standard index. A failed branch lookup never silently falls back to the standard index.
8. **Given** a selected repository entry advertising several package URLs, **When** the chart is downloaded, **Then** the first URL is used, matching the CLI, without reordering URLs or automatically trying another location.
9. **Given** a repository with several chart names and versions, **When** the user lists entries, finds a chart by name or exact version, or requests chart information, **Then** they receive the same entry metadata as the CLI's list, search, and info workflows as programmatic data; unversioned exact-name lookup returns all matching versions in repository order, exact-version lookup returns only the first matching entry, and listing uses the CLI's case-insensitive name ordering.

---

### User Story 4 - Inspect and preview a chart before changing resources (Priority: P2)

An SDK user reviews chart metadata, resolved resources, dependencies, and proposed apply or delete actions as returned data before deciding to execute them.

**Why this priority**: A packaged application should retain the existing Apply ability to validate and review intended changes programmatically.

**Independent Test**: Inspect and preview both operations on a local chart with platform access disabled, then compare the results with direct Apply preparation of its files and effective values. Repeat with an invalid template and check source attribution.

**Acceptance Scenarios**:

1. **Given** a valid local chart and complete render inputs, **When** the user inspects it or previews apply or delete, **Then** metadata, resolved resources, dependency information, and planned actions are returned without platform requests or mutations.
2. **Given** a repository chart, **When** inspection or preview requires retrieval, **Then** repository requests may obtain the package, but no platform resource request is made and no planned action is reported as completed.
3. **Given** invalid metadata, an unreadable values source, an undefined template value, duplicate resource identities, or a dependency cycle, **When** preparation runs, **Then** it fails before platform mutations with the relevant chart source, template path, or values source identified.
4. **Given** a chart template using an existing rio or Ansible filter, **When** the chart is prepared with the same context as direct Apply use, **Then** the resolved document values and scalar types agree with the existing renderer.

### Edge Cases

- An explicitly supplied empty values mapping counts as a supplied source: bundled defaults are not loaded. An omitted or empty sequence of values sources uses the bundled values.
- A chart without `values.yaml` can be prepared with explicit values; preparing it without explicit values fails with the missing bundled values source identified. An existing empty defaults mapping is valid.
- Missing or invalid `Chart.yaml`, missing `templates/`, or no supported template files is an invalid chart. Valid template files that all render to empty documents follow the existing Apply empty-collection behavior.
- Templates are discovered recursively in deterministic relative-path order. Only manifest formats supported by the existing Applier are selected; metadata, values files outside `templates/`, documentation, and unrelated assets are not resource manifests.
- Unsafe paths and links in local chart sources or packaged contents must not read or write outside the selected chart root. Malformed, truncated, or structurally ambiguous packages fail before resource execution.
- A permanent resource failure preserves completed outcomes and uncertain writes exactly as direct Apply use does; the Chart layer does not claim rollback.
- Supplied encrypted secrets require explicit use of the existing decryption helper before chart preparation. Chart operations do not implicitly invoke decryption or CLI authentication.
- Changing values can change rendered resource identities. Deletion acts on the identities rendered from its supplied chart version and values; it does not discover a previous installation's inputs.
- Chart retrieval and resource execution failures must release owned temporary files while leaving caller-owned directories, archives, input data, and clients intact.
- Concurrent live operations on one prepared chart and a client of the wrong execution mode follow the existing Applier rejection behavior.
- Branch paths preserve embedded `/` and percent-encode spaces, query delimiters, and non-ASCII characters exactly as the CLI does. A non-empty branch selects the constructed branch index in preference to a supplied repository override; an empty branch follows ordinary repository selection.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to prepare a chart from a local directory, a local packaged archive, or a repository name with an optional exact version. Equivalent contents and inputs MUST produce equivalent prepared resources. Covered by Story 1, scenario 1, and Story 3, scenarios 1–4.
- **FR-002**: A chart MUST expose its declared name and version and optional descriptive metadata, and MUST contain valid `Chart.yaml` metadata and a `templates/` directory with at least one supported manifest file. Required names and versions MUST be non-empty strings. Repository selection and package metadata MUST agree on name and version. Invalid structure or mismatched identity MUST fail before resource operations. Covered by Story 3, scenarios 1 and 3, Story 4, scenario 3, and the chart-structure edge cases.
- **FR-003**: Chart preparation MUST select supported manifest files recursively under `templates/` in deterministic relative-path order and preserve document order within each file. Files outside that directory and unsupported assets MUST be excluded. Covered by Story 3, scenario 4, and the template-discovery edge case.
- **FR-004**: When no explicit values sources are supplied, preparation MUST use the chart's bundled `values.yaml`. When one or more explicit sources are supplied, preparation MUST use only those sources as values input. Explicit sources MUST retain existing Apply ordering and merge behavior; an empty mapping MUST count as an explicit source. Covered by Story 1, scenarios 1–3, and the values edge cases.
- **FR-005**: Users MUST be able to provide the same values, secrets, explicit platform template context, and optional device-interface resolution inputs accepted by the existing Applier. Rendering, reserved namespaces, rio filters, Ansible filters, and resource validation MUST retain their existing behavior. Chart preparation MUST NOT implicitly decrypt secrets. Covered by Story 1, scenario 4, Story 4, scenario 4, and the encrypted-secrets edge case.
- **FR-006**: Chart apply and delete MUST preserve existing Apply lifecycle semantics, including resource coverage, scope resolution, dependency ordering, retention, readiness settings, worker settings, capability validation, and empty-collection behavior. Covered by Story 1, scenarios 1 and 5, Story 2, scenario 2, and the empty-document edge case.
- **FR-007**: Chart operations MUST return existing structured Apply results and expose existing execution failures, partial progress, cancellation behavior, and latest settled result without losing resource details or claiming automatic rollback. Covered by Story 1, scenario 6, Story 2, scenario 3, and the permanent-failure edge case.
- **FR-008**: Synchronous and asynchronous chart workflows MUST support equivalent chart sources, rendering inputs, settings, inspection, previews, apply, and delete. Asynchronous acquisition and execution MUST allow unrelated application work to progress and settle outstanding work before cancellation returns. Covered by Story 2, scenarios 1–3.
- **FR-009**: Live operations MUST use the exact compatible client supplied by the caller for that call, preserve caller-owned data and client configuration, and leave the client open. Sequential reuse MUST retain existing Apply isolation of scope and execution state; concurrent operations on one prepared chart MUST be rejected under the existing contract. Covered by Story 1, scenario 6, Story 2, scenario 4, and the client-mode edge case.
- **FR-010**: Users MUST be able to inspect chart metadata, rendered documents, resources, and dependencies and preview apply or delete as structured data. Local preparation with complete caller-provided context MUST require no network access. Inspection and previews MUST issue no platform requests; repository retrieval is permitted when explicitly selecting a remote chart. Covered by Story 4, scenarios 1–2.
- **FR-011**: Repository selection MUST support the fixed standard index, branch-specific indexes, and a caller-selected index location. Exact version requests MUST select the first entry matching that version. An unversioned selection MUST choose the first entry for the requested chart in repository order, matching the CLI, and provide a non-fatal diagnostic when several entries match. Selection MUST NOT sort versions or infer a latest version. Unknown names and absent versions MUST produce actionable errors. Covered by Story 3, scenarios 1–3 and 6–7.
- **FR-012**: Retrieval MUST validate index and archive contents before exposing a prepared chart. Network failures, unsuccessful responses, unusable package locations, malformed metadata, and corrupt packages MUST produce errors identifying the requested chart or source and the failed stage, without starting resource operations. The selected entry's first advertised package URL MUST be used, matching the CLI, without automatic URL fallback. Covered by Story 3, scenarios 3 and 8.
- **FR-013**: Loading a chart MUST reject package paths or links that escape its selected root or access external files. It MUST NOT overwrite caller files during extraction. Covered by Story 3, scenario 5, and the unsafe-source edge case.
- **FR-014**: Temporary artifacts owned by chart acquisition MUST be released on success, failure, and cancellation once no longer needed, while prepared data remains usable for inspection and subsequent operations. Caller-owned sources MUST remain unchanged. Covered by Story 1, scenario 6, Story 2, scenarios 3–4, Story 3, scenario 3, and the cleanup edge case.
- **FR-015**: Chart preparation errors MUST retain usable source attribution for values and template failures, duplicate identities, and dependency cycles. No invalid chart preparation may begin a platform mutation. Covered by Story 4, scenario 3.
- **FR-016**: Public documentation MUST demonstrate local, standard-repository, and branch-preview chart use, explicit version selection, the defaults-versus-explicit-values rule, supplied secrets and context, sync and async apply/delete, recreation, repository entry listing and lookup, inspection, previews, and programmatic failure handling without requiring rio CLI installation or configuration. Covered by the independent tests for Stories 1–4.

- **FR-017**: Users MUST be able to construct a branch-specific repository index URL and select that repository for chart lookup and loading in both execution modes. The fixed branch base MUST be `https://chartsbranch.blob.core.windows.net/charts-per-branch`; the branch is appended with `/` and unreserved characters (letters, digits, `-._~`) preserved and other characters percent-encoded as in the CLI, followed by `/incubator/index.yaml`. A non-empty branch MUST take precedence over a repository override; absent or empty branches MUST preserve ordinary repository selection. Covered by Story 3, scenarios 6–7.

- **FR-018**: Chart apply MUST support the CLI recreation behavior: run delete before apply using identical chart inputs and settings, create fresh execution state for each phase, and stop if the delete phase fails or is cancelled. Recreation preview MUST expose both planned phases without platform requests. Outcomes and failures from each phase MUST remain available under the existing Apply result contracts. Covered by Story 1, scenario 7, and Story 2, scenarios 1–4.
- **FR-019**: Chart behavior MUST have parity with the rio CLI for valid repository selection, package selection, branch URL construction, defaults and explicit file values, template rendering, apply, delete, recreation, and previews. Controlled reference cases MUST verify repository ordering, first-URL use, branch encoding, and delete-before-apply behavior against the CLI, in addition to existing template parity cases. SDK-specific client ownership, structured results, asynchronous behavior, and safe package loading MUST retain the existing requirements. Covered by Stories 1–4 and SC-001 through SC-009.
- **FR-020**: Users MUST be able to retrieve repository entries, list available chart versions, find entries by exact chart name with optional exact version, and inspect their metadata as programmatic data with the same selection and ordering behavior as the CLI's list, search, and info workflows. Repository metadata MUST preserve name, version, package URLs, and optional description and creation time. These workflows MUST support the fixed index, a repository override, and branch selection in both execution modes. Covered by Story 3, scenario 9.

### Explicit User and Project Constraints

- The implementation MUST have behavioral parity with the rio CLI Chart implementation. The fixed standard index and branch repository base may be hard-coded constants.
- Chart support MUST wrap the existing `Applier` and `AsyncApplier` classes; template rendering, resource lifecycle execution, and scheduling remain responsibilities of those classes.
- Chart orchestration MUST remain a separate higher-level helper under the project constitution. This feature adds no platform API operations, changes no existing request or response models, and does not alter `Client` or `AsyncClient` operation contracts. Both execution modes and existing Apply input, options, inspection, result, and error contracts are affected through composition only.
- Public chart inputs, outputs, and failure behavior must meet the constitution's documentation and typing requirements. Implementation must satisfy the declared Python compatibility and pinned Ruff checks. No constitution amendment is required.

### Key Entities

- **Chart**: A named, versioned bundle of application templates, bundled values, and optional descriptive metadata.
- **Chart source**: A caller-selected directory, packaged archive, or repository entry identifying the bundle to load.
- **Repository entry**: A chart name, exact version, ordered package URLs, and optional description and creation time advertised in a standard, branch-preview, or caller-selected repository index.
- **Effective render inputs**: Either bundled values or ordered caller-supplied values, plus secrets, explicit platform context, and any device-interface information.
- **Prepared chart**: A validated chart and resolved resource collection available for inspection and lifecycle operations.
- **Operation outcome**: The existing Apply per-resource results, planned actions, failures, and partial progress produced for the chart's resources.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For postgis, gateway, and gostproxy, at least two documented input sets per chart produce identical resource document content, scalar types, and order through chart use, direct template use, and the existing CLI-rendered reference cases in both execution modes, with zero unexplained differences.
- **SC-002**: All acceptance cases for bundled defaults, explicit replacement, ordered values merging, secrets, and template context pass in both execution modes, including an explicit empty values mapping.
- **SC-003**: Every tested apply and delete case has the same resource actions, dependency constraints, retention behavior, and outcome categories as direct template execution; every tested local preview makes zero network requests and every remote preview makes zero platform requests.
- **SC-004**: All directory, local archive, and controlled repository cases for equivalent chart contents produce the same prepared resource collection. Every tested missing, mismatched, or corrupt chart source fails before any platform mutation. Every tested unversioned request selects the same first repository entry as the CLI, including a non-fatal diagnostic when several entries match.
- **SC-005**: During delayed asynchronous retrieval and resource execution, an unrelated application task progresses before completion. Every cancellation case leaves zero background chart or resource operations running after return and zero owned temporary artifacts remaining after cleanup.
- **SC-006**: Every tested invalid source and unsafe package reports an identifiable source or failed stage, changes zero caller-owned files, and starts zero platform mutations. Every tested partial resource failure retains its confirmed and uncertain work information.
- **SC-007**: A developer following the documented examples can prepare, inspect, preview, apply, and delete a chart in each execution mode and distinguish successful, planned, and failed actions using returned data without installing rio CLI or parsing terminal output.

- **SC-008**: Standard and branch repository selection, exact and unversioned entry selection, first-package-URL selection, repository listing/lookup metadata, and recreation produce the same observable decisions as the CLI for 100% of controlled reference cases in both execution modes. A failed delete phase starts zero apply operations.
- **SC-009**: Branch URL construction matches the CLI exactly for all reference cases, including `feature-x`, `bug/fix some`, `feat?oops`, and `bran©h@!`; every branch lookup uses the resulting branch index without falling back to the standard index.

## Assumptions

- The compatibility reference is the inspected local rio CLI checkout at `~/Projects/Work/rapyuta-io-cli`, revision `27bb77bb912705b58a5de0a2e99848dc023ba322`, particularly `riocli/chart/chart.py`, `riocli/chart/util.py`, and the chart apply/delete commands. The package examples are in `~/Projects/Work/rapyuta-charts`, revision `94e456aea0dcdd7d4493aa57662cc0b8815df0ef`.
- The reference Chart workflow uses bundled defaults only when no explicit values are supplied. This specification deliberately retains that observable rule rather than introducing automatic layering of defaults under supplied values.
- Local directories and local archives extend the reference's download workflow to make the package abstraction usable offline. Packaged charts use the existing compressed tar format and contain a single identifiable chart root with the same layout as a local directory.
- Branch repository URL construction is in scope and follows `riocli/chart/util.py` and its unit tests. Branch selection identifies the source of a prepared chart; subsequent apply, delete, inspection, and previews operate on that same selected chart. This does not require adding branch flags to the reference CLI delete command.
- The standard repository index is the fixed URL `https://rapyuta-robotics.github.io/rapyuta-charts/incubator/index.yaml`, matching the reference CLI. It may be hard-coded as a constant; no discovery or configuration mechanism is required for that URL. The existing CLI ability to override the index location remains supported.
- Unversioned selection preserves the CLI's first-entry behavior, including its non-fatal ambiguity diagnostic. Exact versions preserve first-match selection. Repository order is authoritative; the SDK does not infer or sort a latest version.
- Chart lifecycle and rendering depend on the existing Applier feature and the rendering parity feature in `specs/001-sdk-applier/spec.md` and `specs/002-apply-render-parity/spec.md`. They introduce no additional managed resource kinds or platform capabilities.
- Repository list, exact-name search, and info behavior are included as programmatic data for CLI parity; terminal tables, prompts, colors, and spinners remain outside scope. Chart creation/publishing, dependency-chart management, installation history, upgrades, rollback, and release tracking are outside scope. Recreation is included through the Chart wrapper and delegates delete followed by apply to the existing Applier classes.
- CLI parity applies to chart selection, packaging, rendering, and lifecycle decisions; SDK authentication, caller-owned clients, structured diagnostics, explicit secret decryption, and safe archive loading retain their established contracts. CLI presentation and accidental failure modes are not required.
- Authentication, target scope, and client ownership remain caller responsibilities. Filter context needing external information must be supplied under the existing rendering contract; Chart introduces no implicit platform lookup.
- Users deleting a chart supply the same chart version and identity-affecting values used to apply it. Chart packaging does not record prior installation values or discover resources from a release record.
