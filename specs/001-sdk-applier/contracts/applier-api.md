# Contract: Applier Public API

This is an additive Python-library contract for implementation, not an existing executable API. Model definitions and validation are in [data-model.md](../data-model.md).

## Imports and construction

Public convenience imports from `rapyuta_io_sdk_v2`: `Applier`, `AsyncApplier`, `ManifestSource`, `ApplierOptions`, `ReadinessOptions`, `ResourceScope`, `ResourceContext`, `ApplierResult`, `ResourceOutcome`, `ApplierExecutionError`, `ApplierValidationError`, `decrypt_secret_file`, and `async_decrypt_secret_file`. Complete identity/context/inspection/result models are also available under `rapyuta_io_sdk_v2.models`; helper errors under `rapyuta_io_sdk_v2.apply.errors`.

```python
Applier(
    source: ManifestSource,
    *,
    options: ApplierOptions | None = None,
)

AsyncApplier(
    source: ManifestSource,
    *,
    options: ApplierOptions | None = None,
)
```

`ManifestSource` is a frozen dataclass with keyword fields `files`, `resources`, `values`, `secrets`, and `rio`, all optional with empty defaults. Path inputs accept `str` or `Path`; resources accept the participating SDK resource model instances; ordered value/secret sources accept mappings or plain YAML/JSON paths. Construction snapshots input iterables. An empty source is valid.

Constructors accept only ManifestSource and ApplierOptions, perform common local preparation, and produce source-aware parsing/model/identity/graph errors without a client, authentication, or platform access. They do not select a lifecycle operation or reject a valid resource because some alternative operation is unsupported. Each apply/delete call or preview validates that requested operation's capabilities and payload requirements; live calls also receive their client and reject a wrong-mode client before work. Read its configuration into an execution-local scope snapshot and use that exact instance for every platform call in the operation. Client creation, timeout/transport settings, authentication, and cleanup remain caller responsibilities. Neither facade stores the client between calls or accepts a configuration-only construction path.

Inspection has no client argument; apply/delete clients may be omitted for preview. Live non-empty operations require a supplied configured client and required scope/authentication; missing clients fail before any platform request. Empty collections return an empty successful result without transport construction. Sequential calls with the same or different clients are supported; concurrent operations on the same facade raise ApplierUsageError before work starts. Parallel independent facades are allowed.

## Methods

```python
# Both facades expose local synchronous inspection.
inspect() -> InspectionResult
last_result: ApplierResult | None

# Applier methods are blocking.
apply(client: Client | None = None, *, dry_run: bool = False) -> ApplierResult
delete(client: Client | None = None, *, dry_run: bool = False) -> ApplierResult

# AsyncApplier execution methods are awaitable.
async apply(client: AsyncClient | None = None, *, dry_run: bool = False) -> ApplierResult
async delete(client: AsyncClient | None = None, *, dry_run: bool = False) -> ApplierResult
```

The facade uses constructor options for worker/readiness/scope settings; clients are supplied to execution methods and are not constructor options; callers create another facade to choose different settings. `inspect` returns independent copies of resolved manifest data, resource identities, and a directed dependency graph, including external references. It does not render images or print output. Returned manifest data may contain explicitly resolved secret values; the SDK never prints it automatically. Values supplied under secrets, including SOPS-decrypted mappings, are ordinary input data. Applier does not track secret provenance or provide secret-specific redaction of representations, validation errors, platform errors, or chained tracebacks.

Sync execution checks for a running event loop in the calling thread before creating a coroutine or starting platform work, including sync dry runs. It directs such callers to AsyncApplier. Resource methods themselves use ordinary sync calls, not nested runners. AsyncApplier accepts a supplied AsyncClient only, and awaits its native platform calls. Source preparation remains local synchronous work.

## Preparation, scope, and ordering

Normalize manifest kind spelling before validating the supplied modeled input; preserve names and versions. Construction checks common local kind/model/identity/alias/graph validity. At apply preflight, including apply preview, select/revalidate SecretCreate/UserGroupCreate as request variants rather than losing creation-only fields; inspection/delete do not demand creation-only credentials on valid response instances. Do not globally tighten SDK response-model validation. Empty YAML documents are ignored. A JSON file supplies exactly one resource object.

Resolve explicit options scope over the supplied client's configured defaults. Validate that the execution method received a client and necessary live context before any platform request. Rebind identities to this call's effective scope and build fresh lookup/GUID/server-routing caches; never reuse context resolved with a previous client. Explicit routing metadata/options still constrain the target and mismatches must fail preflight. Apply endpoint-specific context arguments without mutating those defaults. Known metadata routing conflicts fail preflight. Project payloads receive the selected organization on private copies; RoleBinding domains stay grant data rather than changes to the selected project.

Managed dependencies use canonical structured identity and known local GUID aliases. External references are never scheduled for mutation. Fresh sorter state is built for every operation. Apply finishes prerequisites before dependents; delete reverses those edges. A ready cohort completes before the next cohort starts. At most `options.workers` resources are active, including readiness checks. The HTTP connection pool may further limit remote concurrency. Sync transport calls are blocking and have no request-overlap guarantee; async calls can overlap.

Cycle detection, duplicates, unsupported operations, and invalid required fields fail before writes. Organization delete is unsupported unless retention explicitly skips it. Retention keeps a resource without automatically retaining its dependencies. Delete absence is a non-fatal `absent` outcome. Deletion of unmanaged dependencies never occurs.

## Preview contract

`dry_run=True` performs operation capability validation and reports ordered intended actions and retention. It performs zero platform requests, creates no client, and never invokes SOPS. Caller-supplied secret values, including an explicitly decrypted mapping, can be used during preparation.

Apply preview reports create-or-update, create-or-exists, update-only, or grant policy without asserting that the object currently exists. Delete preview reports delete/revoke or retained. It does not perform live GUID/routing-name/readiness lookup; those are execution-time work.

## Result and error contract

Successful calls return an immutable ApplierResult with one outcome per input resource, in stable input order. Every call updates `last_result` only after all workers settle. Preflight failure leaves the previous result intact because no operation has started.

Statuses and fields follow [data-model.md](../data-model.md). Outcomes contain identities, actions and failure metadata rather than raw resource payloads. This result structure does not imply secret-specific diagnostic redaction. Before each resource call, the scheduler retains its fresh MutationJournal and passes the exact instance through ResourceContext.progress. Named write helpers record progress before/after each invocation, so settlement can recover prior completed actions even if a later write or readiness check raises without returning ResourceOutcome. Compute write uncertainty from uncertain or unfinished attempts and do not double-count successful returned outcomes. The recorder never stores clients or payloads and is excluded from context dump/repr/schema; details are in [resource-progress.md](resource-progress.md).

Errors:

| Error | Raised when | Caller-accessible data |
| --- | --- | --- |
| ApplierValidationError | File/manifest/template/identity/graph input invalid | source, category, involved identities where available |
| ApplierUsageError | Wrong client type, sync call in a running loop, or concurrent call on one facade | corrective guidance |
| UnsupportedResourceOperationError | Known resource cannot perform the requested operation | identity, operation |
| MissingResourceContextError | Required client, live authentication/scope, or routing context unavailable | resource/operation and required context names |
| ApplierExecutionError | Worker/lifecycle/readiness failure after execution starts | result: ApplierResult; structured causes identifying resource and stage |
| ReadinessError | Terminal readiness state or bounded checks exhausted | identity, last safe state, terminal/exhausted category |

TaskGroup worker groups are translated to ApplierExecutionError after settlement; consumers need not unpack ExceptionGroup for ordinary failures. A worker independently raising CancelledError is incomplete work, not successful completion: stop scheduling, settle peers, and raise an identified execution error unless the coordinator is already handling caller cancellation. Never mark that graph node done or leave the sorter waiting indefinitely. Cancellation is not translated into an ordinary execution failure: propagate the original asyncio.CancelledError after cleanup and expose the settled result through `last_result`. Cancellation outcomes identify cancelled workers, blocked descendants, and other unstarted work. Do not rollback or retry arbitrary writes.

Supplied clients remain open and unchanged on success, failure, and cancellation. Applier settles its workers, but never closes, replaces, or constructs client transports. Callers manage client lifecycle and must keep a supplied AsyncClient on the appropriate event loop. Execution retains the client only in call-local worker/context state; after settlement, the facade holds no client reference. Results contain resolved identities, not client objects or credentials. Scope and source snapshots are immutable during execution.

## Acceptance obligations

- FR-001–FR-005: standalone typed construction, supported loading, reserved context merging, zero-platform preparation, and mapped operation coverage.
- FR-009–FR-010, FR-015–FR-017: dependency/reverse ordering, finite workers, async progress, failure and cancellation cleanup, ownership, source immutability, and repeat execution.
- FR-013–FR-014: truthful previews and stable per-resource structured results.
- FR-018: documented sync/async usage and result handling without rio imports.
