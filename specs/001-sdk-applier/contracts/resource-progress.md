# Contract: Resource Mutation Progress

This is a proposed SDK contract for the progress channel used by [resource methods](resource-interface.md) and the [Applier scheduler](applier-api.md). It resolves how partial writes survive a method raising before returning an outcome.

## Types and signatures

Export MutationAttempt and MutationJournal from rapyuta_io_sdk_v2.models; define them in models/progress.py. MutationAttempt is a frozen validated model with sequence: positive non-boolean integer, action: created/updated/deleted/revoked, and state: started/completed/rejected/uncertain. MutationJournal is a concrete typed recorder, not a Pydantic platform payload or an arbitrary callback.

```python
MutationJournal()
begin(action: MutationAction) -> int
complete(sequence: int) -> None
reject(sequence: int) -> None
mark_uncertain(sequence: int) -> None
snapshot() -> tuple[MutationAttempt, ...]
```

MutationAction is the Literal union created/updated/deleted/revoked. Allocate monotonically increasing positive sequence numbers beginning at one. An empty journal has an empty snapshot. Each begin creates one started attempt; complete/reject/mark_uncertain transition that attempt exactly once into its corresponding terminal state. Unknown sequence IDs, overlapping pending writes, or contradictory terminal transitions are programmer errors raised before a subsequent platform write. Snapshot entries and their tuple are immutable and detached from further recorder changes.

ResourceContext gains optional progress: MutationJournal | None = None. Keep its scope/readiness frozen. Use SkipJsonSchema over the entire optional progress field with Field(exclude=True, repr=False), and arbitrary_types_allowed on ResourceContext only. The supplied instance is retained by reference for this operation; it is absent from model_dump, model_dump_json, validation/serialization JSON Schema, and repr. No shared SDKModel or existing resource payload configuration changes.

## Ownership

The scheduler allocates a fresh journal for each managed resource operation before calling its lifecycle method, retains it outside that method, and passes it explicitly in the node's ResourceContext. Different workers and subsequent apply/delete calls use different journals. Nested helpers for one resource share that exact recorder; they never clone it. Clients remain separate arguments and are never stored in a journal or context.

Direct resource apply/delete with no recorder create a local journal used to build their outcome. Direct create/update helpers also support an explicitly supplied recorder while preserving their existing validated response return type. A direct caller needing partial progress after failure/cancellation supplies and retains a fresh MutationJournal through ResourceContext.progress and reads snapshot afterwards. Callers must not share or reuse one journal across distinct resource operations. No global state, ContextVar lookup, introspection, inferred methods, or external progress callback is required.

## Write boundaries and transitions

1. Complete payload validation and local routing arguments before recording a write attempt. Record started immediately before invoking the named client write.
2. Immediately after the client returns a validated successful response, mark completed before another await, readiness check, or write. Each actual write is recorded once in its named helper, rather than again in outer policy.
3. Mark rejected only when a documented typed error conclusively establishes a no-effect rejection, including the creation conflict/permission-denial fallback or deletion of an already absent object. A rejected create followed by successful update has two attempts but only one completed action, updated.
4. For cancellation, transport interruption, response-validation failure, or another exception whose write effect cannot be confirmed, mark uncertain and re-raise the original exception. Journal updates perform no await, callback, logging, or platform operation, so cancellation cannot interrupt completion bookkeeping between a successful response and recording it.
5. Grant success records created; exact revocation records revoked. Reads, readiness checks, retention, and absence established by lookup do not create attempts. Cancellation during readiness does not change earlier completed attempts.

Do not classify every non-success server response as a definitive rejection. If the SDK cannot establish a no-effect outcome, the result remains uncertain; this does not authorize retry, rollback, or compensating deletion.

## Settlement and errors

After workers settle, the scheduler reads every retained journal even if the resource call raised before returning ResourceOutcome. Construct completed_actions from completed attempts in sequence order; set write_uncertain when any attempt is uncertain or remains started. This unfinished-attempt fallback prevents lost uncertainty even if resource cleanup exits early. Preserve the resource's failed/not_completed status and failure metadata independently of its prior successful writes.

Successful ResourceOutcome values use the same snapshot. Reconcile them with the retained journal rather than duplicating completed_actions. Final results contain immutable values, not journal references, clients, requests, responses, or raw exceptions; release journals and execution contexts after result construction.

Ordinary collection failure exposes the immutable result through ApplierExecutionError.result. Caller cancellation remains the original asyncio.CancelledError after settlement; the caller reads Applier.last_result. Direct callers read their retained journal after ordinary exceptions or the original cancellation. Neither path adds a partial-progress wrapper to CancelledError or attaches mutable progress/credentials to exceptions.

## Required validation

Include Project create success followed by update failure, create/update success followed by readiness failure, cancellation during a write versus later readiness, rejected-create/update fallback, unconfirmed response-validation failure, successful delete/revoke followed by another worker failure, direct-call cancellation with a supplied journal, isolated concurrent/repeated operation journals, immutable snapshots, and context dump/repr/schema exclusion. Use controlled clients; no platform credentials are needed.
