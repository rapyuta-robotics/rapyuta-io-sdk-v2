# Revision Context and Batch Lifecycle Contract

**Interfaces**: [sdk-interface.md](sdk-interface.md) | **Data**: [data-model.md](../data-model.md)

## Public surface

```python
class Revision:
    def __init__(
        self,
        client: Client,
        tree_name: str,
        *,
        options: RevisionOptions | None = None,
        parent: str | None = None,
    ) -> None: ...

    @property
    def keys(self) -> dict[str, ConfigValue]: ...

    @property
    def revision_id(self) -> str | None: ...

    def store(
        self,
        key: str,
        value: ConfigContent,
        *,
        metadata: dict[str, str] | None = None,
    ) -> None: ...

    def __enter__(self) -> Revision: ...
    def __exit__(self, exc_type, exc_value, traceback) -> bool: ...


class AsyncRevision:
    # Same constructor/options/properties/store surface, using AsyncClient.
    async def __aenter__(self) -> AsyncRevision: ...
    async def __aexit__(self, exc_type, exc_value, traceback) -> bool: ...
```

These are signatures only; implementations must fully annotate exception/traceback parameters and use Google-style documentation. `ConfigContent` is a recursive supported-content alias: JSON primitives, dates/datetimes, lists, and string-keyed mappings. Declare it with the options/helper types in `models/configtree_operations.py`. `AsyncRevision.store()` remains a normal synchronous method because it stages local data and performs no I/O.

`keys` is getter-only but its returned dictionary and entries are mutable. Each instance owns a distinct initially empty dictionary. It is the authoritative pending write set; no hidden per-key request queue exists. The context snapshots routing/options locally and never owns/changes the caller's client.

## Construction and entry

- Construction validates local options/name/scope and prepares commit defaults if needed; a directly used context with commit enabled and no message supplied uses `Created revision through rapyuta-io-sdk-v2`. It performs no platform I/O. Supported dictionary edits occur inside the context body.
- Entry creates one fresh revision with `create_revision`. If `parent` is supplied, use `ConfigTreeRevision(parent=parent)`; otherwise retain platform default parent behavior. A parent belongs to the destination tree and must satisfy the platform's committed-parent requirement.
- `revision_id` is `None` until a response supplies a nonempty metadata GUID, then remains available on the context for recovery. Missing GUIDs are failures and do not initiate storage.
- Entry returns the context itself. A second entry or attempted second finalization is invalid; contexts cannot be reused.

## Editing pending keys

`store()` validates and encodes a logical leaf, then adds/replaces a `ConfigValue` in `keys` without a request. Strings stay text; other values become JSON, with ISO date conversion and rejection of unsupported/non-finite values. Encode UTF-8 bytes as base64, compute the platform MD5 checksum with non-security usage, set byte-based content length, `kv` content type, and `644` permissions. Metadata is validated and copied, including an explicitly empty dictionary.

Direct dictionary assignment requires a valid `ConfigValue` storage entry; raw logical values are not accepted. Inside the context body, users may replace entries, set their metadata, delete pending names, or clear the dictionary. To change logical content without stale derived fields, call `store()` again. Direct encoded-data changes must update the checksum consistently or fail final validation. Edits through retained references after the body exits are outside the supported contract; no special guard is added to prevent them.

Deleting/clearing affects pending writes only. If the initialized revision inherited a key from its parent, removing that name from the pending dictionary does not remove the inherited key. Remote deletion remains outside scope.

## Normal exit

1. Capture the final dictionary as an independent snapshot. Validate entry names, present key-value data, required checksum/content type, and strict field types. Dump previously created entries to plain fields first, preserving `exclude_unset`; do not trust validation of existing mutable model instances.
2. Construct a validated `ConfigValues` request from that snapshot. Preserve aliases, explicit empty metadata, and omitted optional fields. Require a present content length matching decoded byte count. Preserve valid Merge payload fields without re-encoding or re-serializing their values; inconsistent source lengths have already failed before destination creation.
3. If nonempty, invoke `put_keys_in_revision` exactly once. If empty, invoke no key-write operation. There are no per-key calls, chunked batches, or retries.
4. Require `APIResponse.success=True` and no nonempty `error` for a submitted batch. Missing, null, or false success is failure. Never commit after such a response.
5. If requested, commit once using the prepared typed commit body, after successful batch acknowledgement or the empty-batch skip.
6. Close the context locally and return false from the exit method. The calling Import/Merge workflow may now select the head; context exit itself never updates it.

Do not repeatedly flush after closure. Async exit prepares the validated request before awaiting storage, then awaits storage and commit in sequence. The contract makes no promise about edits through retained references during exit.

## Exceptional exit and recovery

| Failure boundary | Operations allowed afterward | Recovery context |
| --- | --- | --- |
| Preparation or scope failure | None | No created revision |
| Initialization fails or lacks GUID | None | ID may be unknown; stage `create` |
| Exception/cancellation in body | No batch, commit, or head update | Known ID, stage `body`; revision may remain |
| Final snapshot validation | No batch, commit, or head update | Known ID, stage `validate` |
| Batch request/envelope | No commit or head update | Known ID, stage `store`; remote write may be uncertain |
| Commit | No head update | Known ID, stage `commit`; commit may have completed remotely |
| Head selection in workflow | No further mutation | Known ID, stage `head`; head outcome may be uncertain |

Preserve the original exception type and traceback; annotate `configtree_revision_id`, `configtree_stage`, and an exception note. Exit never suppresses a body error or cancellation. An exception handler used solely for these annotations must re-raise and use the narrowest feasible catches; any necessary broad catch must have a documented Ruff rule-specific justification rather than disable checks globally.

Cancellation can arrive during creation, storage, commit, or head selection. Propagate it immediately, attach any already known identifier, and start no subsequent platform stage. Do not use `shield`, swallow cancellation, convert it to a domain error, or dispatch rollback requests. A thread doing local document preparation may finish after Import cancellation; it performs no remote mutation and its result is discarded.

## Mandatory acceptance evidence

Verify dictionary identity and independent contexts, edits within the context body, invalid mutated model instances, exact zero/one batch counts, unchanged source payloads, and create/store/commit/head ordering. Cover body, validation, explicit envelope, transport, commit, and head failures plus cancellation at each async boundary. Both contexts use the same pure validation/encoding rules and equivalent observable outcomes.
