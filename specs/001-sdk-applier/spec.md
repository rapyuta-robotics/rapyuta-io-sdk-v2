# Feature Specification: Reusable SDK Applier

**Feature Branch**: `feat/apply`

**Created**: 2026-10-09

**Status**: Draft

**Input**: User description: "The rio CLI implements the Apply-family of commands through the Applier class. The implementation is CLI specific and cannot be re-used in other projects through the SDK. Add the Applier implementation in the SDK with support for Async and Sync. Use the newer TaskGroup API for implementing workers instead of ThreadPool. For the Applier implementation, the Resource classes need to be updated with the required interface methods for Applier to use. Reference: ~/Projects/Work/rapyuta-io-cli."

## Clarifications

### Session 2026-10-09

- Q: What support should the SDK provide for encrypted secret files? → A: Provide an optional helper that invokes the `sops` command for decryption, which callers can use to supply secret values to Applier. (User-provided clarification.)
- Q: Do decrypted values need special protection after being supplied to ManifestSource? → A: No. Once returned and supplied to ManifestSource, they are ordinary input values, with no secret-specific redaction or protection in Applier. Confidentiality guarantees apply only to the SOPS helper’s own diagnostics and handling of plaintext. (User-provided clarification.)
- Q: How should Resource models share implementation? → A: Use a ResourceMethods mixin for common behavior, with explicit resource overrides for special cases and no introspection. (User-provided refinement.)
- Q: When should callers supply the client? → A: Pass Client or AsyncClient to each apply/delete call, not the constructor. Non-empty live execution requires a client; offline inspection and preview may omit it. Client creation and cleanup stay with the caller. (Planning decision following user feedback.)
- Q: How must partial mutation progress survive resource failure or cancellation? → A: Record each write independently of the resource method's final return; preserve confirmed steps and identify unconfirmed write effects in settled results while propagating caller cancellation unchanged. (Planning clarification of analysis finding U1.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Apply resources from a synchronous application (Priority: P1)

An application developer uses the SDK to apply a collection of resource manifests without installing or invoking the rio CLI. The developer supplies platform context and receives an inspectable outcome for every resource.

**Why this priority**: Reusable apply behavior is the central capability currently unavailable to downstream SDK users.

**Independent Test**: From an application that depends only on the SDK, apply a package and a deployment that depends on it against controlled platform responses; verify the package completes first and both outcomes are returned.

**Acceptance Scenarios**:

1. **Given** valid manifests for absent resources, **When** a synchronous caller applies them, **Then** resources are created in dependency order and each created resource has an identifiable outcome.
2. **Given** an existing resource that supports updates, **When** its manifest is applied, **Then** the resource is updated and reported as updated; an existing resource whose apply behavior excludes updates is reported as already existing without replacement.
3. **Given** two packages with the same name and different versions and deployments referencing each version, **When** they are applied together, **Then** both versions are processed and each deployment waits for its own referenced version.
4. **Given** creation is denied but updating is permitted for an updatable resource, **When** apply is requested, **Then** an update is attempted; a denied operation is never reported as already existing merely because updates are unsupported.
5. **Given** an organization or project manifest, **When** it is applied, **Then** organization membership updates and project creation, update, scope resolution, and provisioning checks follow the supported behavior in the resource coverage table.
6. **Given** a role binding without a resource name, **When** it is applied, **Then** its role, subject, and domain identify the grant, and its prerequisites are processed first.
7. **Given** a client passed to apply or delete with chosen transport settings and platform context, **When** execution succeeds, fails, or is cancelled, **Then** Applier uses that exact client, preserves its context, and leaves it open for the caller.

---

### User Story 2 - Apply resources from an asynchronous application (Priority: P1)

A developer integrates the same workflow into an application already performing asynchronous work. Independent resources can progress together within a selected worker limit while the application remains responsive.

**Why this priority**: Async support is an explicit requirement and must provide the same usable feature set as sync support.

**Independent Test**: Apply independent resources and one dependent resource while an unrelated application task runs. Verify overlapping work, the worker limit, dependency ordering, continued application progress, and outcome equivalence with sync execution.

**Acceptance Scenarios**:

1. **Given** equivalent inputs and platform responses, **When** sync and async callers apply or delete resources, **Then** they receive equivalent resource outcomes and failures, allowing different completion order for independent resources.
2. **Given** three independent resources and a worker limit of two, **When** async execution starts, **Then** two can progress together, no more than two resource operations are active, and their dependents wait for successful prerequisite completion.
3. **Given** one resource fails permanently, **When** the operation fails, **Then** dependent work does not start, outstanding work is settled or cancelled before control returns, and completed outcomes and the failing resource remain inspectable.
4. **Given** an async operation is cancelled during work or a readiness wait, **When** cancellation completes, **Then** no worker continues issuing platform requests after the operation has returned.
5. **Given** a synchronous entry point is called from an application with active asynchronous execution, **When** that use cannot be supported, **Then** the caller receives an actionable error directing them to the asynchronous entry point and no resource operation starts.
6. **Given** a prepared collection without fixed routing scope and two clients targeting different scopes, **When** the same Applier is executed sequentially with each client, **Then** each call uses its supplied client and freshly resolved scope without carrying server-resolved identifiers or routing names from the previous call.

---

### User Story 3 - Delete managed resources safely (Priority: P2)

An application developer removes resources described by manifests while respecting dependencies and resources marked for retention. The same workflow can be composed with apply to recreate resources.

**Why this priority**: Deletion and recreation are part of the existing Apply-family and complete the reusable lifecycle.

**Independent Test**: Delete a dependency chain containing one retained resource and one absent resource. Verify reverse dependency order, retention, and distinct deleted, retained, and absent outcomes.

**Acceptance Scenarios**:

1. **Given** a deployment depends on a package in the manifest set, **When** delete is requested, **Then** the deployment is deleted before the package.
2. **Given** a resource has the label `rapyuta.io/deletionPolicy: retain`, **When** delete is requested, **Then** no deletion is issued for it and its retained outcome is returned.
3. **Given** a resource is already absent, **When** delete is requested, **Then** absence is reported as a non-fatal outcome and eligible deletion continues.
4. **Given** deletion fails permanently for a dependent resource, **When** reverse-order execution reaches that failure, **Then** its prerequisites are not subsequently deleted and the failure identifies that resource.
5. **Given** a successful delete phase, **When** the caller applies the same resource collection again, **Then** an independent apply phase runs successfully without exhausted dependency state from the prior operation.
6. **Given** a role binding grant, **When** delete is requested, **Then** that grant is revoked using its binding identity without granting it again.

---

### User Story 4 - Validate and preview manifests before execution (Priority: P2)

A developer loads and renders manifests, inspects the resources and dependencies, and previews apply or delete without platform changes or CLI presentation requirements.

**Why this priority**: Preview and validation allow applications to review the same intended operations they later execute.

**Independent Test**: Load a multi-document manifest with supplied values and secrets, inspect its resolved resources and dependency relationships, and preview both operations with no platform access. Separately invoke the optional decryption helper with a controlled encrypted secret file and verify its returned values can be supplied to the same workflow.

**Acceptance Scenarios**:

1. **Given** YAML or JSON manifest files and ordered value sources, **When** they are loaded, **Then** values are rendered, supported resources are validated, and the resolved manifests and dependencies are available to the caller.
2. **Given** supplied secret values and explicitly supplied project and organization template context, **When** templates are resolved, **Then** those values are usable without reading rio's local configuration or automatically invoking the decryption helper.
3. **Given** valid resources, **When** apply or delete runs in dry-run mode, **Then** intended actions and retention decisions are returned with zero platform requests and no authentication requirement.
4. **Given** malformed input, an unsupported resource kind, duplicate identities, or a dependency cycle, **When** the collection is prepared by the constructor, **Then** an error identifies the input or resources involved without platform access. Unsupported lifecycle operations and apply-specific creation requirements are checked when apply/delete or their previews are requested, before any platform mutation; preparing an Organization for supported apply does not fail because its deletion is unsupported.
5. **Given** an empty file or an empty YAML document, **When** input is loaded, **Then** it contributes no resource; a collection with no resources produces an empty successful result.
6. **Given** an encrypted YAML or JSON secret-values file and a configured local SOPS installation, **When** a caller explicitly invokes the SDK decryption helper, **Then** it returns a mapping that can be supplied to Applier under `secrets`, leaves the encrypted source unchanged, and makes no platform requests.
7. **Given** the decryption command is unavailable, the file cannot be read or decrypted, or the decrypted content is invalid or is not a mapping, **When** the helper is invoked, **Then** the caller receives an actionable error identifying the source and failure category without decrypted secret values in SDK-generated diagnostics.
8. **Given** equivalent encrypted inputs, **When** the helper is used through its sync and async entry points, **Then** both return equivalent secret values or failure categories; async use allows unrelated application work to continue, and cancellation settles the decryption process before returning.

### Edge Cases

- Duplicate identities across documents or files must be rejected; distinct package versions must remain distinct.
- Missing kind, required identity fields, or a package version must fail validation. Role bindings use composite identity and do not require a metadata name.
- Resource-kind capitalization must be normalized consistently for identity and dependency matching without altering names or versions.
- Self-dependencies and cycles must fail before execution and identify the resources involved.
- References outside the manifest set refer to existing platform resources; they must not cause implicit creation or deletion. A readiness requirement still applies to an external reference.
- A readiness lookup returning no matching resources must not be treated as readiness success; every required resource must be present and ready.
- Readiness exhaustion, terminal failure states, and cancellation must identify the affected resource and stop dependent execution.
- Invalid worker limits or retry settings must fail before execution; a limit of one must execute serially.
- Retention skips one resource's deletion; it does not infer retention for other resources. Any platform rejection of later deletions must be surfaced.
- A later operation on the same prepared collection must rebuild execution state and preserve caller-owned manifests and platform context.
- Partial execution is not transactional: successful platform changes remain visible in the result after a later failure.
- An encrypted secret file path containing spaces or shell metacharacters must be treated as a literal file path, not as additional commands.
- Decryption failures must not return partial decrypted values as successful input. The helper must not print or automatically persist decrypted values; missing SOPS credentials must produce an actionable error.
- Loading supplied plain secret values or running a dry run must not implicitly invoke SOPS. Callers may explicitly decrypt first when a preview needs encrypted secret values.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The SDK MUST provide reusable sync and async Applier workflows for loading, inspecting, applying, deleting, and previewing supported resources, with no dependency on rio CLI imports, configuration, terminal interaction, or process exits. Covered by Stories 1–4.
- **FR-002**: Each non-empty live apply/delete call MUST accept a caller-supplied Client for sync operations or AsyncClient for async operations, with explicit platform scope where needed. Constructors MUST accept only source and preparation/execution options, not clients. Applier MUST use that exact client, leave client creation and cleanup to the caller, and MUST NOT persist or switch the caller's selected organization or project as a side effect. Missing client or required execution context MUST produce an actionable error before platform requests. Offline inspection and dry runs MAY omit a client. Covered by Story 1, scenarios 5 and 7, and Story 4, scenarios 2–3.
- **FR-003**: Applier MUST load `.yaml`, `.yml`, and `.json` files, including multiple YAML documents, and support caller-supplied resource instances so applications need not write manifests to disk. Empty documents MUST be ignored; unsupported extensions and invalid manifests MUST identify their source. Covered by Story 4, scenarios 1, 4–5; the instance path MUST produce the same outcomes as equivalent file input.
- **FR-004**: Applier MUST render supplied values and secret values before resource validation. Later value sources MUST override earlier sources at matching keys while preserving unrelated nested keys. Secret values MUST be available under `secrets` and MUST be treated as ordinary input values after injection, including values returned by SOPS; no special redaction or protection is required in Applier. Explicitly supplied platform template context MUST be available under `rio`. Resolved manifests MUST be inspectable without printing them. Covered by Story 4, scenarios 1–2; acceptance includes merging two sources with overlapping and distinct nested keys.
- **FR-005**: Applier MUST support the resource kinds and operations in the coverage table. Constructors MUST reject unsupported resource kinds during local preparation. Each apply/delete call, including its preview, MUST validate the requested lifecycle capabilities and operation-specific payload requirements before platform mutations, except explicit retention skips. Constructors MUST NOT reject a valid resource solely because a different lifecycle operation is unsupported. Covered by Story 4, scenario 4.
- **FR-006**: Each supported Resource class MUST expose public, documented interface methods for stable identity, direct dependency discovery, and supported create, update, and delete behavior in both sync and async use. It MUST declare unsupported operations explicitly. Resources without dependencies MUST provide an empty dependency collection. Covered by Stories 1–3; conformance MUST be checked for every coverage-table resource.
- **FR-007**: Identity and dependency references MUST use the same normalized kind and identity rules. Ordinary named resources MUST include kind and name; packages MUST additionally include version; role bindings MUST use their role, subject, and domain references. Identities MUST be interpreted within the target scope, duplicates MUST be rejected, and different package versions MUST never overwrite each other. Covered by Story 1, scenarios 3 and 6, and Story 4, scenario 4.
- **FR-008**: Apply MUST create absent resources, update existing resources where supported by the coverage table, and report existing resources unchanged where apply excludes updates. On creation conflict or creation permission denial, an available update MUST be attempted; permission denial MUST remain a failure if updating cannot succeed. Organization apply MUST update the identified organization. Covered by Story 1, scenarios 1–5.
- **FR-009**: Apply MUST complete prerequisites before starting their dependents; delete MUST process the reverse dependency order. References absent from the input MUST be treated as external prerequisites without being mutated as part of the collection. Covered by Stories 1 and 3, scenario 1, and the external-reference edge case.
- **FR-010**: Execution MUST support a configurable positive worker limit, defaulting to six, and allow independent resources to progress concurrently in async execution while respecting that limit. A limit of one MUST preserve serial execution. Async platform I/O and readiness waits MUST allow unrelated application work to progress. Covered by Story 2, scenario 2 and its independent test.
- **FR-011**: Required readiness waits MUST distinguish successful submission from readiness. Newly created disks and networks, project updates requiring provisioning, and deployment prerequisites explicitly marked to wait MUST be checked until ready, terminally failed, or exhausted. Callers MUST configure a bounded number of readiness checks and a non-negative interval; at least one check MUST be performed when waiting is required. Covered by Story 1, scenario 5, and the readiness edge cases; acceptance includes delayed success, missing resources, terminal failure, and exhausted checks in both modes.
- **FR-012**: Delete MUST honor `rapyuta.io/deletionPolicy: retain`, report already absent resources without failing the operation, and report unsupported deletion explicitly. Role binding deletion MUST revoke the identified grant. Covered by Story 3, scenarios 2–3 and 6, and Story 4, scenario 4.
- **FR-013**: Inspection and dry runs MUST validate inputs and dependency ordering, expose resolved resources and dependency relationships as data, and identify intended actions and retention skips without making platform requests. A preview MUST NOT claim that an intended action has already succeeded. Covered by Story 4, scenarios 1–4.
- **FR-014**: Execution MUST expose structured per-resource outcomes distinguishing created, updated, already existing, deleted, already absent, retained, planned, failed, and work not completed after failure or cancellation. Errors MUST identify resource, operation, and cause and preserve inspectable completed outcomes. Confirmed mutation steps within a resource MUST remain visible if its later write or readiness check fails or is cancelled; writes whose external effects cannot be confirmed MUST be identified as uncertain rather than reported as having no effect. Covered by Stories 1–3 and Story 4, scenario 3.
- **FR-015**: Permanent failure MUST stop new dependent work, settle or cancel outstanding workers before returning, and propagate failure to the caller. Cancellation MUST propagate after cleanup. Execution MUST NOT claim rollback or issue automatic compensating deletions. Covered by Story 2, scenarios 3–4, and Story 3, scenario 4.
- **FR-016**: Sync and async workflows MUST support the same resource kinds, inputs, lifecycle semantics, preview behavior, worker and readiness settings, and outcome categories. Unsupported sync use within active asynchronous execution MUST fail before starting work and direct the caller to async use. Covered by Story 2, scenarios 1 and 5.
- **FR-017**: Preparing or executing a collection MUST preserve caller-owned resource data, existing model serialization behavior, and client operation contracts. Repeated preview, apply, and delete calls MUST use fresh execution state, including scope, lookup caches, and server routing names derived from that call's client. Applier MUST NOT retain the supplied client between calls. Covered by Story 3, scenario 5, and the repeated-operation edge case; acceptance includes unchanged input data and existing request/response compatibility checks.
- **FR-018**: Public documentation MUST demonstrate standalone sync and async apply, delete, dry-run, worker settings, readiness settings, resource interfaces, supported kinds, and programmatic result/error handling. It MUST also demonstrate explicitly invoking the secret-file decryption helper, supplying its returned mapping to Applier, and the required local command and credential setup. The examples MUST run without rio installed. Covered by the independent tests for Stories 1–4.
- **FR-019**: The SDK MUST provide an optional secret-file decryption helper with sync and async entry points. On explicit invocation, it MUST decrypt a caller-selected YAML or JSON file and return a mapping accepted as Applier secret values, without modifying the encrypted source or automatically printing or persisting plaintext. Applier MUST continue to accept plain secret values without invoking the helper. Missing executable, unreadable file, decryption failure, and invalid or non-mapping decrypted content MUST produce actionable errors identifying the source and failure category without secret values in the helper’s own diagnostics. Its returned mapping is ordinary caller data; injecting it into ManifestSource does not extend the helper’s confidentiality guarantees to Applier. Async use MUST permit unrelated work to progress and settle the decryption process before cancellation returns. Covered by Story 4, scenarios 2 and 6–8, and the secret-file edge cases.

### Resource Coverage

The initial scope is the intersection of the CLI Applier's supported kinds and the SDK's existing resource capabilities. Read, list, and readiness operations are included when needed for identity resolution or lifecycle completion. Both sync and async workflows must cover this table.

| Resource kind | Required apply behavior | Required delete behavior | Existing request/response models and platform operations affected |
| --- | --- | --- | --- |
| Organization | Update an existing organization identified by GUID | Explicitly unsupported | Organization; get/update organization |
| Project | Create or update; resolve GUID by name when needed; preserve feature-specific provisioning behavior, including Docker cache configuration requiring update | Resolve GUID and delete | Project, ProjectList; list/get/create/update/delete project |
| Package | Create; report existing versions unchanged | Delete the specified version | Package, PackageList; list/get/create/delete package |
| Deployment | Create after prerequisites and requested readiness waits; report an existing deployment unchanged | Delete by name | Deployment, DeploymentList; list/get/create/delete deployment |
| Disk | Create and await readiness; report existing disks unchanged | Delete by name | Disk; get/create/delete disk |
| Network | Create and await readiness; report existing networks unchanged | Delete by name | Network; get/create/delete network |
| StaticRoute | Create or update | Delete by name | StaticRoute; create/update/delete static route |
| Secret | Create or update | Delete by name | SecretCreate, Secret; create/update/delete secret |
| UserGroup | Create or update; resolve GUID when needed | Resolve GUID and delete | UserGroupCreate, UserGroup, UserGroupList; list/create/update/delete user group |
| Role | Create or update | Delete by name | Role; create/update/delete role |
| RoleBinding | Grant the identified role to its subject in its domain | Revoke that grant | RoleBinding, RoleBindingList, BulkRoleBindingUpdate; list/get/update role binding |
| ServiceAccount | Create or update | Delete by name | ServiceAccount; create/update/delete service account |

### Explicit User and Project Constraints

These constraints preserve requirements explicitly supplied by the user and project governance; they do not prescribe additional implementation design.

- Worker orchestration MUST use the newer TaskGroup API instead of ThreadPool. This applies to workers serving both public execution modes.
- The optional secret-file decryption helper MUST invoke the installed `sops` command for decryption, as explicitly requested by the user. It MUST reside outside the platform client modules and MUST NOT require rio CLI configuration.
- The separate higher-level Applier helper MUST compose the public `Client` and `AsyncClient` methods. Those clients MUST retain one-to-one platform operation semantics; async resource operations MUST use awaitable I/O.
- ResourceMethods MUST provide common resource behavior through a mixin, with explicit overrides for resource-specific operations and special cases. Runtime introspection, method-name inference, and reflection-based operation discovery MUST NOT be used.
- The affected resource methods and public outcome contracts MUST be typed and document inputs, outputs, and failure behavior. Request and response payloads MUST retain the SDK's validated models, field aliases, and omitted-field semantics.
- Implementation MUST comply with the existing constitution's declared Python compatibility, module separation, and pinned Ruff checks. This specification requires no constitution amendment.

### Key Entities *(include if feature involves data)*

- **Manifest collection**: Caller-supplied files or resource instances representing intended platform resources, with source information for diagnostics.
- **Rendering context**: Ordered values, secret values, and explicit platform template context used to resolve manifests.
- **Encrypted secret-values file**: A caller-selected YAML or JSON values source decrypted only by explicit helper invocation; its returned mapping feeds the rendering context without becoming a platform resource.
- **Resource**: A validated platform object with a kind, identity, scope, direct dependencies, lifecycle capabilities, and optional retention policy.
- **Dependency relationship**: A prerequisite reference that establishes apply order and reverse delete order; it may reference a resource managed outside the collection and may require readiness.
- **Operation settings**: Apply or delete selection, preview mode, worker limit, and bounded readiness-check settings.
- **Operation outcome**: Resource identity, intended or completed action, completion category, and error details when applicable; a failed collection preserves successful partial outcomes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A standalone application completes apply, delete, and preview using only the SDK for 100% of the resource operations in the coverage table, with unsupported operations producing explicit errors.
- **SC-002**: Sync and async execution produce equivalent resource outcomes for 100% of the acceptance cases under equivalent platform responses.
- **SC-003**: Every prerequisite in the acceptance collections completes before its dependent starts during apply, and every dependent precedes prerequisite deletion; both versions of a same-name package are processed without loss.
- **SC-004**: Every preview and rejected preflight case makes zero platform mutations; previews make zero platform requests, and every retained resource receives zero deletion requests.
- **SC-005**: During asynchronous execution with three independent resources and a worker limit of two, two operations can overlap, active resource work never exceeds two, and unrelated asynchronous application work continues during platform waits. Synchronous execution honors the worker setting and lifecycle outcomes but does not guarantee overlapping HTTP requests.
- **SC-006**: Every permanent failure or cancellation case identifies incomplete work, preserves completed outcomes, and leaves zero workers issuing requests after return to the caller.
- **SC-007**: A developer can run the documented sync and async examples and distinguish creation, update, existing resources, deletion, retention, preview, and failure using returned data without parsing terminal output.
- **SC-008**: For both execution modes, 100% of valid encrypted YAML/JSON secret-file acceptance cases yield values usable in manifest rendering with zero platform requests and no source-file changes. Every invalid-input or decryption-failure acceptance case produces a distinguishable error, and the SOPS helper’s own diagnostics and automatically written files contain zero decrypted secret values. This guarantee ends at the returned mapping and does not apply to subsequent ManifestSource or Applier processing.

## Assumptions

- The reference implementation is `~/Projects/Work/rapyuta-io-cli/riocli/apply/parse.py`, supported by `riocli/model/base.py`, `riocli/apply/util.py`, and the CLI's resource wrappers. Observable lifecycle behavior is the compatibility baseline; accidental CLI defects, such as discarding dependencies or re-granting bindings during deletion, are not requirements.
- The first release covers the 12 kinds listed above. CLI Device provisioning relies on the older SDK and has no matching resource/client support here, so Device management and adding new platform operations are outside this feature. Existing Device references may remain external prerequisites passed through to the platform.
- Other SDK resources, such as configuration trees, managed services, files, users, and OAuth clients, are outside this initial Apply-family scope.
- Migration of the CLI to the new SDK Applier is separate work; this feature makes the SDK reusable and does not modify the reference CLI repository.
- Apply-family coverage includes reusable rendering, inspection, dependency data, apply, delete, dry runs, and the optional SOPS decryption helper. CLI prompts, spinner output, graph image rendering, filesystem discovery conventions, and other command integrations remain caller responsibilities. Callers can compose delete and apply to implement recreation.
- Template values and secret values can be supplied as mappings or ordered plain YAML/JSON value sources. Callers may explicitly use the SDK SOPS decryption helper for encrypted secret-values files or supply values decrypted by other means. SOPS installation and its decryption credentials remain caller-managed, and callers not using this helper do not require SOPS. Optional CLI-specific template filters are outside the initial scope; standard template rendering and explicit `rio`/`secrets` context are required.
- Each execution has a single caller-selected target scope, using explicit per-resource scope where the platform contract requires it. Managing multiple organizations or projects concurrently is outside this initial scope.
- Retry settings govern readiness checks, matching their purpose in the reference workflow; this feature does not introduce general retries for arbitrary failed writes. The default readiness budget is 50 checks at six-second intervals, matching the CLI's default settings; polling stops earlier on success or terminal failure.
- External prerequisite existence may be validated by the platform at execution time. Local preflight does not require platform reads, and readiness checks must verify all required external resources when waiting is requested.
- Dependency scheduling need not preserve completion order among independent resources. On failure, some independent work may already have completed; callers receive that information and decide recovery.
