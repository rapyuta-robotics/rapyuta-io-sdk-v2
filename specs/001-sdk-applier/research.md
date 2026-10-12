# Research: Reusable SDK Applier

Date: 2026-10-09. Scope: FR-001–FR-019 in [spec.md](spec.md).

All planning unknowns are resolved. The decisions below combine read-only inspection of this SDK and `~/Projects/Work/rapyuta-io-cli` with primary documentation. No platform changes were made.

## 1. Sync and async execution with TaskGroup

**Decision**: Provide `Applier` and `AsyncApplier`. Both use one dependency scheduler implemented with `asyncio.TaskGroup`. A sync worker invokes the supplied Resource's synchronous lifecycle method directly; an async worker awaits its asynchronous counterpart. `Applier` runs the scheduler with `asyncio.run`, checking for an active loop in the calling thread before constructing a coroutine. Async callers use `AsyncApplier`.

**Rationale**: This honors supplied `Client` transports, subclasses, and test doubles. The spec requires overlapping resource operations for async use; synchronous HTTP blocks and does not promise overlapping requests. Shared scheduling gives consistent dependency, failure, and result behavior without thread workers. Python's runner cannot be nested inside an active loop in the same thread. [Python runners](https://docs.python.org/3.13/library/asyncio-runner.html)

**Alternatives considered**: ThreadPoolExecutor and `to_thread` violate the requested worker direction. Replacing a supplied `Client` with an `AsyncClient` loses its transport behavior. A persistent private loop complicates lifecycle and repeated calls without adding a required capability.

## 2. Bounded scheduling, failure, and cancellation

**Decision**: Build a fresh `graphlib.TopologicalSorter` for every run. Only managed resources become execution nodes; external references remain dependency metadata. A coordinator obtains each ready cohort and creates at most `workers` queue-draining workers in a TaskGroup. It calls `done` only after all successful resource outcomes in that cohort, including required readiness. Reverse managed edges for delete. A shared stop flag prevents taking more queued work after permanent failure.

**Rationale**: Cohort barriers match the reference CLI behavior and avoid requiring tasks for every resource simultaneously. TaskGroup waits for its children and cancels peers when a worker fails; convert its grouped errors to one documented execution exception carrying a complete result snapshot. External cancellation remains `CancelledError`; expose the settled snapshot through `last_result`. A child independently raising CancelledError does not trigger TaskGroup failure on its own: the worker/coordinator must turn unexpected child cancellation into an identified execution failure, stop peer work, and avoid releasing dependents. [Python TaskGroup](https://docs.python.org/3.13/library/asyncio-task.html#task-groups), [graphlib](https://docs.python.org/3.13/library/graphlib.html)

**Alternatives considered**: Reusing a prepared sorter prevents repeat calls. Adding absent prerequisites to the sorter implicitly creates unmanaged nodes. Releasing dependents at submission time can race provisioning. Dynamic scheduling offers finer throughput but is unnecessary for the required behavior.

## 3. Common resource mixin with explicit overrides

**Decision**: Use a field-free ResourceMethods mixin for common identity, empty dependencies, capability access, retention, apply policy, unsupported-operation defaults, and delete outcome handling. Models declare typed ClassVar capabilities and explicitly override supported client operations, dependency extraction, version/composite identity, and special lifecycle workflows. Normal method dispatch and named helper functions provide reuse without introspection. A typing-only Resource protocol supports static checking. Preserve fields, aliases, response optionality, schemas, and legacy list_dependencies compatibility.

**Rationale**: The user explicitly permits common mixin implementation with overrides and prohibits introspection. Capability constants and declared hooks make supported behavior explicit, while common policies avoid repeating conflict/update fallback and retention/absence logic. Package and RoleBinding identity and Project/RoleBinding workflows override relevant defaults. Deep copies retain caller data and omitted-field state. [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/)

**Alternatives considered**: Defining every common method directly on every model duplicates policy and can drift across kinds. Dynamic method-name inference or getattr/hasattr/inspect-based dispatch is unnecessary and prohibited. A fixed kind-to-model map remains appropriate only for manifest parsing; it does not discover client operations.

**Resource ownership refinement (2026-10-12)**: Ordinary paired endpoint calls now
live directly in resource model methods. Keeping single-call adapters in apply
modules added delegation without sharing resource-specific behavior. Scope
reconciliation, private copies, exact routing option types, and mutation recording
remain shared utilities. Secret and UserGroup models own request conversion;
UserGroup exact GUID lookup remains a separate multi-call helper. Project cache
provisioning, StaticRoute canonical resolution, and RoleBinding matching remain
workflow helpers. Disk, Network, Project, and Deployment own pure
`readiness_state()` methods; generic polling consumes a typed readiness interface
and handles missing observations. Model fields and wire schemas remain unchanged.
This refines the implementation ownership in decision 3 while retaining its
field-free mixin, explicit dispatch, client ownership, and serialization rules.

## 4. Clients supplied to each operation

**Decision**: Constructors take source/options only. Each non-empty live apply/delete call receives Client or AsyncClient explicitly, uses that exact instance, and reads an execution-local scope snapshot. Preview may omit the client. Applier never constructs, replaces, closes, or retains clients between calls. Resolve scope, GUIDs, lookup caches, and server routing names fresh per operation; explicit source/options scope still constrains reuse. Client settings, authentication, lifecycle, and async event-loop affinity remain caller-managed.

**Rationale**: Passing clients at execution time separates local preparation from remote context and permits a prepared collection to run sequentially with different clients without rebuilding templates. It also prevents stored configuration or resolved routing data from silently leaking into another operation. Shared worker scheduling only needs the client for that call. HTTPX documents explicit client lifecycle management. [HTTPX lifecycle](https://www.python-httpx.org/async/#opening-and-closing-clients)

**Alternatives considered**: Constructor-injected clients couple preparation to one execution context. Lazy client creation duplicates setup/ownership and discards customization. Retaining previous clients or cross-call platform lookup caches risks targeting the wrong scope. Hidden login and client factories are unnecessary.

## 5. Loading, templates, and secret values

**Decision**: Add `jinja2>=3.1.6`; retain PyYAML and existing validated models. Render with `ImmutableSandboxedEnvironment`, `StrictUndefined`, explicit `autoescape=False`, and no filesystem loader or CLI filters. Merge plain value mappings recursively in caller order, replacing scalars/lists at overlapping keys; then install explicit `rio` and `secrets` reserved namespaces. Parse YAML with safe loading and JSON with the standard parser. Validate manifest-specific requirements without tightening optional response schemas globally. Secret values injected into ManifestSource, including SOPS-decrypted mappings, are ordinary input data with no special redaction or protection; the SOPS helper’s confidentiality guarantees cover only its own handling and diagnostics.

**Rationale**: Standard expressions remain usable; missing values fail with source context instead of silently producing invalid names. Jinja documents undefined-value handling and sandbox behavior; the selected minimum includes its attribute-lookup sandbox fix. Templates remain caller-selected local inputs; the sandbox is not a resource isolation boundary. [Jinja API](https://jinja.palletsprojects.com/en/stable/api/), [Jinja sandbox](https://jinja.palletsprojects.com/en/stable/sandbox/), [Jinja changes](https://jinja.palletsprojects.com/en/stable/changes/)

**Alternatives considered**: Ad hoc substitution cannot preserve template expressions. Importing Ansible, SOPS, or rio during normal loading makes unrelated callers depend on optional tooling. Deep merging lists has no stated semantic and would be surprising.

## 6. Optional SOPS helper

**Decision**: Export `decrypt_secret_file` and `async_decrypt_secret_file`. Validate `.yaml`, `.yml`, or `.json`, resolve the readable file to an absolute path, and invoke an argument vector equivalent to `sops decrypt --input-type yaml --output-type json /absolute/file.yaml` (use JSON input type for `.json`). Return a string-keyed mapping after successful exit and JSON validation. Capture both pipes; never invoke a shell or request in-place/output-file mode.

**Rationale**: Decryption is explicit and its output feeds Applier's secret-values input. SOPS documents stdout decryption with explicit formats; these options let the SDK avoid plaintext files. Installation and credentials remain caller-managed. [SOPS programmatic decryption](https://getsops.io/docs/usage/advanced/#encrypting-and-decrypting-from-other-programs), [SOPS operations](https://getsops.io/docs/usage/common-operations/)

**Alternatives considered**: Automatically decrypting all secret inputs contradicts the optional helper. Shell strings misinterpret filenames. A Python SOPS reimplementation duplicates key-provider behavior. Passing raw stderr or parser excerpts into exceptions can disclose values.

**Cancellation/failure contract**: Sync uses `subprocess.run` with captured pipes; async uses `asyncio.create_subprocess_exec` and `communicate`. Shield ownership of process creation so cancellation during spawn cannot orphan a process. On cancellation, terminate, allow one second for exit, then kill if necessary; drain/reap before propagating cancellation, including repeated cancellation during cleanup. Error fields contain source, category, optional exit code, and generic corrective guidance, never output or plaintext-bearing exception chains. [Python subprocess](https://docs.python.org/3.13/library/subprocess.html), [Python async subprocesses](https://docs.python.org/3.13/library/asyncio-subprocess.html)

## 7. Lifecycle mapping and special cases

**Decision**: Implement only the 12 kinds in the spec. Ordinary mutable resources create first, then update on conflict or denied creation. Package, Deployment, Disk, and Network apply do not update existing resources. Organization is update-only. RoleBinding grants and revokes through `BulkRoleBindingUpdate`. Exact scoped lookups paginate and reject ambiguous matches.

**Rationale/evidence**:

- `client.py` and `async_client.py` already expose corresponding typed operations for all covered kinds; the exact matrix is in [resource contracts](contracts/resource-interface.md).
- Both `create_secret` and `update_secret` require `SecretCreate`, returning `Secret`. Keep Docker credentials in the request rather than downcasting to a response model.
- User-group creation requires `UserGroupCreate`; updates use `UserGroup` carrying a resolved GUID. Preserve explicit membership role data when converting to the update model.
- CLI `riocli/role/bind.py` sends `newBindings`; `riocli/role/unbind.py` resolves the grant and sends only `oldBindings`. Its Applier wrapper instead passes the wrong request model and repeats a grant during delete; do not port that defect.
- CLI `riocli/project/model.py` states Docker cache is update-only. For an absent cache-enabled project, create a copied base manifest with caching disabled, then update the full manifest and wait. The CLI fallback sends caching to create; correct this orchestration defect. Record partial successful mutations if later provisioning fails.
- CLI `riocli/static_route/create.py` documents backend organization suffixing, and deletion uses the canonical response name or an organization-short-GUID suffix. Keep logical identity separate from server routing name, resolve `organization_short_guid` explicitly or via an execution-only organization read, and never append a suffix twice.

**Alternatives considered**: Porting wrappers verbatim repeats observed defects. Adding resource orchestration to transport clients violates the constitution. Adding newer SDK kinds or Device provisioning broadens the specified scope.

## 8. Readiness and verification

**Decision**: Check immediately, then sleep only between remaining checks; default 50 polling rounds per readiness target at six-second intervals. Any paginated lookup within a round is part of that round, not an additional readiness check. Every target has its own check budget; at most checks minus one sleeps occur for each target. Sync resource methods use blocking sleep; async counterparts use `asyncio.sleep`. Disk is ready at `Available` or `Released`, failed at `Failed`. Network is ready at phase `Succeeded`, terminal at `Stopped`, `FailedToStart`, `FailedToUpdate`, error status, or image-pull code `DEP_E153`. Project is ready at `Success`, terminal at `Error`. Required Deployment references are ready at status `Running`, terminal at `Error`/`Stopped` or failed/stopped phases. Missing resources/status remain pending until exhaustion, never success.

**Rationale**: These states are evidenced by SDK models and CLI `riocli/disk/util.py`, `riocli/network/util.py`, and `riocli/deployment/model.py`. Retrieve every requested reference without filtering failure states away. Callers see per-resource completion only after readiness, while successful earlier writes remain recorded.

**Alternatives considered**: Treating empty lists as success repeats the CLI's vacuous `all` behavior. Retrying arbitrary writes changes semantics and risks duplicates. Waiting indefinitely prevents predictable failure handling.

## Validation targets carried into implementation

These are verification work, not unresolved product choices: request/response serialization for all mapped operations; Docker cache bootstrap/update; canonical StaticRoute routing; exact RoleBinding grant/revoke payloads and GUID-only lookup; Network terminal states; simultaneous worker failure and repeated cancellation; SOPS spawn cancellation and literal filenames. Controlled client/transport responses establish deterministic contracts; a separately configured test-platform run can corroborate platform-specific routing/provisioning without becoming a prerequisite for offline tests.

## 9. Explicit mutation progress across raised failure and cancellation

**Decision**: Use a concrete MutationJournal passed explicitly through optional ResourceContext.progress. Each scheduler resource operation owns a fresh recorder outside the call. Named write helpers record started/completed/rejected/uncertain states without awaiting, and settlement reads immutable snapshots regardless of the method's return or exception. Direct callers can retain their own supplied recorder. Cancellation propagates unchanged; neither progress recovery nor ordinary failure requires modifying a CancelledError. The exact contract is [resource-progress.md](contracts/resource-progress.md).

**Rationale**: A returned ResourceOutcome cannot carry writes performed before the method raises. A retained recorder makes those effects observable for collection and direct usage and preserves earlier successful Project writes when subsequent update/readiness fails. Only confirmed rejection clears uncertainty; unconfirmed transport/response failures remain uncertain. Typed bookkeeping stores no clients or payloads and introduces no operation introspection.

**Serialization evidence**: A local probe with the installed Pydantic version confirmed that a frozen context can retain an exact arbitrary recorder reference while excluding it from model_dump, model_dump_json, validation/serialization JSON Schema and repr. Use SkipJsonSchema over the entire optional field plus Field(exclude=True, repr=False), with arbitrary_types_allowed on ResourceContext only; do not change SDKModel. Pydantic documents [SkipJsonSchema](https://docs.pydantic.dev/latest/api/json_schema/#pydantic.json_schema.SkipJsonSchema) and [arbitrary type configuration](https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict.arbitrary_types_allowed). This is a design probe, not implemented SDK validation.

**Alternatives considered**: A ContextVar hides ownership and makes direct-call cancellation progress harder to retrieve. A partial-failure exception payload does not cover unchanged caller cancellation without another channel. Arbitrary callbacks can themselves fail after a platform mutation. Putting mutable progress on resource payloads alters wire contracts. A concrete excluded recorder avoids those issues while keeping normal signatures and explicit dispatch.

## 10. Common preparation versus operation preflight

**Decision**: Constructors validate local parsing/rendering, supplied modeled fields, kind/identity/aliases and graph structure. Each requested apply/delete or preview performs lifecycle capability and operation-specific payload validation, with retention exceptions. Live execution alone requires configured client/authentication/scope and fresh scope binding. Preserve response-only Secret/UserGroup instances for inspect/delete; apply performs the creation-request conversion/validation. Preparing an Organization is valid even though deleting it is unsupported.

**Rationale**: Source/options-only construction cannot choose which later lifecycle operation the caller intends. Explicit staging retains zero-platform preparation and permits reusable inspection without treating an unsupported alternative operation as invalid input. SC-005 is also clarified to require overlap only for async execution, consistent with existing Client ownership and blocking sync calls.

**Alternatives considered**: Rejecting any resource with an unsupported operation at construction would exclude valid Organization apply and conflate inspection with mutation. Deferring all validation until workers start risks partial collection writes for locally invalid input. Network lookups at constructor or preview violate offline preparation. Common validation followed by operation preflight avoids all three.
