# Research: Configtree Import and Fast Merge

**Date**: 2026-10-12 | **Specification**: [spec.md](spec.md)

All design questions are resolved. Research used this checkout, the installed rio CLI, locally installed dependencies, and the local platform source. No additional dependency or platform endpoint is needed.

## 1. Workflow placement and public interfaces

**Decision**: Add a `rapyuta_io_sdk_v2.configtree` package exposing `Revision`, `AsyncRevision`, Import/Merge functions, and refspec parsing. Put options models in `models/configtree_operations.py`. Keep client methods as individual platform operations.

**Rationale**: The constitution requires separate orchestration modules and equivalent synchronous/asynchronous contracts. Existing `models/configtree.py` already supplies the wire payloads.

**Alternatives considered**: Adding workflow methods to the clients violates constitution principles II and IV. Depending on rio introduces CLI state, interactive dependencies, and configuration ownership that this feature excludes.

## 2. Metadata splitting and document parsing

**Decision**: Implement shared pure wrapper recognition and splitting. A wrapper has exactly `value` and `metadata`, with dictionary metadata. Traverse ordinary mapping children, stop within recognized wrapper values, and never traverse lists for splitting. Keep extracted metadata as opaque attachments keyed by configuration path; join attachments only at identical flattened content paths. Preserve empty metadata and falsy values.

**Rationale**: Installed rio's `riocli/configtree/import_keys.py::split_metadata` and `util.py::Metadata` establish these semantics. The SDK's `pydantic_source/source.py::_split_metadata` already removes equivalent wrappers. A wrapped mapping flattens afterward, so parent metadata does not propagate to child keys.

**Alternatives considered**: Flattening ordinary metadata dictionaries produces unwanted configuration keys. Treating every object with a `value` field as annotated content changes ordinary data. Recursively splitting wrapper values or list items deviates from rio.

**Decision**: Use the existing PyYAML dependency with a private safe loader that detects duplicate explicitly authored mapping entries before expanding `<<` merges, then preserves YAML override precedence; parse JSON with duplicate-aware object-pair handling. Require one UTF-8 mapping document per file and UTF-8 encodable configuration paths, reject duplicate filename stems and ambiguous content paths, preserve atomic lists and empty nested objects, and normalize dates to ISO strings. Reject cyclic aliases, non-finite numbers, and unsupported YAML values before mutation.

**Rationale**: Import must validate the entire input before creation. Generic parser defaults can silently overwrite authored duplicates, while duplicate checks after YAML merge expansion incorrectly reject valid overrides. Escaped surrogate path characters can collapse to the same key during JSON-mode serialization. Explicit content flattening makes empty-container and list behavior independent of benedict release behavior.

**Alternatives considered**: Using the settings loader directly couples Import to its looser parsing and drops metadata. Import validation remains separate; only wrapper recognition/splitting may be reused by the settings source without changing that source's other behavior.

## 3. Key encoding and mutable validation

**Decision**: A staging `store()` helper creates `ConfigValue` entries: strings remain text; other supported leaves serialize as JSON; encode UTF-8 bytes to base64, compute an MD5 content checksum using `usedforsecurity=False`, set `content_type="kv"`, byte-based `content_length`, and default permissions `"644"`. Merge may decode selected base64 data to validate byte length, then copies valid typed payloads without re-encoding or re-serializing their data.

**Rationale**: rio's `Revision.store` supplies the storage convention. Byte length correctly represents Unicode payload size. MD5 is the platform's artifact identifier, not a security primitive.

**Alternatives considered**: `str()` for collections creates invalid JSON. Re-encoding Merge data can alter checksums or confuse plain strings with JSON. rio's character-count content length is unsuitable for Unicode.

**Decision**: Before final batch submission, deep-snapshot each staged entry to plain Python fields with `exclude_unset=True`, then validate through `ConfigValue`/`ConfigValues` with strict types. Validate key names and required key-value fields locally. Direct payload edits must remain internally consistent; use `store()` to replace logical content with freshly derived encoding/checksum/length. Preserve existing omitted fields and distinguish absent metadata from `{}`. Before Merge creates a destination revision, reject every selected source entry with absent content length or a length different from decoded byte count, including entries at compatible shared keys; identify the key without changing the source payload.

**Rationale**: `SDKModel` enables alias population only, without assignment validation or instance revalidation. A local experiment with Pydantic 2.13.5 showed that `ConfigValues.model_validate` accepts previously constructed `ConfigValue` instances after invalid assignment; validation of their plain mappings rejects those same mutations. An independent snapshot also prevents edits during an awaited batch from changing the submitted payload.

**Alternatives considered**: Globally enabling assignment validation changes existing public contracts. Wrapping live models in `ConfigValues` alone misses invalid mutations. Sending raw dictionaries violates principle III.

## 4. Revision lifecycle and batch storage

**Decision**: Context construction performs no I/O. Entry creates one fresh revision and records its ID. Its read-only `keys` property returns one live mutable dictionary per context. Normal exit validates and snapshots the final dictionary, submits exactly one batch when nonempty, then optionally commits. Empty dictionaries skip key writes. Body failures/cancellation skip finalization. Contexts are single-use; workflows update the head after successful context exit.

**Rationale**: Installed rio's context buffers data and batches it on successful exit. This feature makes that buffer public without CLI revision reuse. Removing a staged entry cannot delete platform-inherited keys.

**Alternatives considered**: Per-key writes violate FR-024. Automatic rollback requires additional operations and cannot guarantee rollback after uncertain remote completion. Chunking a batch would violate the requested one-write contract.

## 5. Scope routing and existing client corrections

**Decision**: Snapshot organization/project GUIDs and route every request using explicit per-call header options. Organization scope uses `with_project=False`; project scope uses `True`. Always include the organization context. Require the relevant configured GUIDs before mutation; never mutate the caller's configuration or close its transports.

**Rationale**: All six existing operations accept these options. `Configuration.get_headers` falls back to configured project GUIDs when an override is `None`, so `project_guid=None` does not select organization scope. The platform gives the project context precedence when both headers are present.

**Alternatives considered**: Temporarily changing client configuration leaks scope across concurrent asynchronous workflows. Creating extra clients would lose the caller's transport settings and ownership.

**Decision**: Correct `AsyncClient.put_keys_in_revision` to the canonical revision URL, removing `/keys/`. Align asynchronous `get_configtree` optional query omission with the synchronous method.

**Rationale**: The synchronous method uses `PUT /v2/configtrees/{name}/revisions/{revision_id}/`. Local platform `v2/configtrees/server/http.go::PutKeysInRevision` and `client/http.go::PutKeysInRevision` establish that route. The current asynchronous `/keys/` path is incompatible. Async tree reads currently send absent selectors/filters; sync omits them. These are existing principle-II parity violations directly relevant to the feature and must be corrected during implementation.

**Alternatives considered**: Private transport calls bypass public clients and violate composition requirements. Keeping divergent paths cannot deliver equivalent workflows.

## 6. Refspecs and milestone pagination

**Decision**: Return a four-field immutable `ConfigTreeRef` from `parse_refspec`. Accept exactly two or three nonempty slash-separated components, with `org`/`proj` scope. Selectors starting with `rev-` denote revision IDs; other selectors denote milestones. Missing selectors use the current head.

**Rationale**: rio's `util.py::parse_ref` establishes selector classification; the spec deliberately rejects ambiguous extra components.

**Decision**: Resolve milestones using `list_revisions`, label selector `rapyuta.io/milestone=<name>`, and `committed=False` (no committed-only filter). Follow positive advancing numeric continuation offsets, verify matching labels and revision IDs, and require exactly one distinct match. Continue after a short page if a token exists; reject repeated/nonadvancing tokens and malformed results. Multiple matches may fail immediately because ambiguity is already established.

**Rationale**: `ListMeta.continue_` is numeric. The platform emits cumulative offsets and zero at exhaustion. Existing `utils.walk_pages` stops at short pages and lacks loop guards; its behavior cannot guarantee milestone uniqueness.

**Alternatives considered**: First-match resolution silently chooses an ambiguous revision. Refactoring all pagination utilities would widen scope unnecessarily.

## 7. Merge compatibility, empty maps, and parents

**Decision**: Compare shared keys' exact stored `data` and `metadata`; retain destination entries for compatible shared keys and copy source-only entries. Report all conflicts before creating a revision. Read key-value content with `include_data=True` and `content_types=["kv"]`. Pin Merge's creation parent to the destination head ID used for the compatibility check.

**Rationale**: rio's `merge.py::is_fast_merge_possible` compares data and metadata; this is key compatibility, not ancestry-based merging. The platform copies a parent's keys at initialization and requires that parent to be committed. Pinning the parent avoids inheriting an unrelated head if the destination changes between read and creation.

**Alternatives considered**: Decoding values before comparison changes rio's equality rules. Overwriting conflicting values or partial merging is excluded. Implicit parent selection could use a different revision from the checked base. Atomic head compare-and-swap is not available through the selected operations; concurrent head changes remain a documented limit.

**Decision**: Require a non-null whole key map in each data-included Merge response. An explicit `{}` remains valid; an omitted or null map and missing data within an individual selected key are errors.

**Rationale**: An omitted map cannot be distinguished from an incomplete data-included response. Treating it as empty could discard source keys or bypass destination conflict checks. The platform's `omitempty` behavior means it must send `{}` for an empty revision to support Merge safely.

## 8. Commit defaults, failures, and cancellation

**Decision**: Prepare nonempty commit author/message before creation whenever committing is requested. Use an explicitly provided commit body first; fill absent author from `client.config.email` or `"rapyuta-io-sdk-v2"`, and absent message from the documented default: `Created revision through rapyuta-io-sdk-v2` for a direct context, or the Import/Merge operation default. Reject explicitly empty author/message. Preserve labels and other caller-supplied fields.

**Rationale**: Local platform DAO implementations require nonempty author/message. rio's fallback depends on operating-system user state, which this SDK must not require.

**Decision**: Preserve original SDK/transport/Pydantic errors and `CancelledError`; annotate known revision ID and failed stage on the original exception and in its notes. Require `success=True` and no nonempty `error` for a submitted batch, even on a successful HTTP status. Do not retry mutations, suppress cancellation, or initiate later publication stages after failure.

**Alternatives considered**: Replacing cancellation with a normal exception breaks task cancellation. Treating every successful HTTP status as workflow success ignores the existing `APIResponse` contract. Automatic retries can duplicate revisions or publish an uncertain result.

## 9. Verification and dependency choices

**Decision**: Keep current dependencies and Python 3.13+ compatibility; test using pytest, pytest-asyncio, and HTTPX MockTransport. Cover pure transformations once, equivalent sync/async workflow outcomes, actual URL/query/header contracts, direct model mutations, batch counts, sequencing, and cancellation. Preserve existing settings-source and low-level model tests. Use Ruff 0.16.9 without rule relaxation.

**Rationale**: These dependencies already exist in `pyproject.toml`, and CI targets Python 3.13 and 3.14. Local installed dependency versions verified during research are Pydantic 2.13.5, PyYAML 6.0.3, benedict 0.30.0, and HTTPX 0.28.1; they are observations, not new pins.

**Alternatives considered**: Introducing an async file library or a CLI dependency adds no required capability. Async Import can use `asyncio.to_thread` for file preparation while platform I/O remains awaitable.
