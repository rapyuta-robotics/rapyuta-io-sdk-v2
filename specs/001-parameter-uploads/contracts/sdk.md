# SDK Contract: v1 Parameters and Upload Helpers

This is the implementation target, not an interface already available in the package. Models are defined in [data-model.md](../data-model.md); transfer requirements are in [storage.md](storage.md). Package identity remains `rapyuta_io_sdk_v2`.

## Configuration

Add `Configuration.core_api_host: str | None = None` as the last dataclass field. Whitespace-only overrides normalize to absent. Store the resolved endpoint in `config.hosts['core_api_host']`.

| Environment | Core endpoint when no explicit override |
| --- | --- |
| `ga` | `https://gaapiserver.apps.okd4v2.prod.rapyuta.io` |
| `qa`, `dev`, `pr*` | `https://{environment}apiserver.apps.okd4v2.okd4beta.rapyuta.io` |
| `local` | `LOCAL_COREAPI_HOST` if set; otherwise unconfigured |

Explicit `core_api_host` wins over environment defaults and the local environment variable. `set_environment()` recomputes the slot consistently with existing host override rules. `Configuration.from_file()` reads optional `core_api_host`; it must not overwrite the existing v2/rip behavior. The host is an absolute HTTP(S) origin; append the Parameter prefix once and avoid duplicate trailing slashes. Local without a core endpoint remains usable for existing v2 operations; only Parameter calls fail before I/O.

Parameter methods resolve the core slot at call time and reuse `config.get_headers(**kwargs)` conventions for authentication, request ID, project, organization, and group. Header metadata supplied through `ParameterUploadMetadata` takes precedence over generic content-type/checksum options for that operation; use `Checksum`, not v2 `X-Checksum`. Helpers require a configured project and auth token before mutations. Direct methods retain per-call `HeaderOptions` overrides.

## Client methods

The following signatures apply to `Client`. `AsyncClient` exposes corresponding `async def` methods with identical arguments and result types, and uses awaitable requests on `self.c`. No new Parameter method calls the legacy synchronous authentication transport.

```text
list_parameter_trees(*, query: ParameterTreeQuery | None = None,
                     **kwargs: Unpack[HeaderOptions]) -> ParameterTreeListResponse
create_parameter_tree(name: str,
                      **kwargs: Unpack[HeaderOptions]) -> ParameterTreeCreateResponse
get_parameter_tree(name: str,
                   **kwargs: Unpack[HeaderOptions]) -> ParameterNodeResponse
put_parameter_node(tree_path: str, body: ParameterNodeWrite,
                   **kwargs: Unpack[HeaderOptions]) -> ParameterNodeResponse
delete_parameter_tree(name: str,
                      **kwargs: Unpack[HeaderOptions]) -> ParameterDeleteResponse
delete_parameter_node(tree_path: str, body: ParameterNodeDelete,
                      **kwargs: Unpack[HeaderOptions]) -> ParameterDeleteResponse
list_parameter_blobs(query: ParameterBlobQuery,
                     **kwargs: Unpack[HeaderOptions]) -> ParameterBlobListResponse
prepare_parameter_upload(tree_path: str, metadata: ParameterUploadMetadata,
                         **kwargs: Unpack[HeaderOptions]) -> ParameterUploadResponse
commit_parameter_upload(tree_name: str, blob_ref_id: str,
                        **kwargs: Unpack[HeaderOptions]) -> ParameterCommitResponse
```

Every method issues one platform operation. All successful payloads are validated through the declared Pydantic response model. Direct methods expose platform errors; dedup status checks, local filesystem reads, transfers, and recreation sequencing belong to helpers.

### Wire mapping

Let `BASE = core_api_host.rstrip('/') + '/api/paramserver'`.

| Method | HTTP path | Request payload | Success response |
| --- | --- | --- | --- |
| `list_parameter_trees` | GET `BASE/tree` | No body; repeated `instances` if supplied by query model | 200 `{data: [tree names]}` |
| `create_parameter_tree` | PUT `BASE/tree/{name}` | No body; server creates a value root | 201 `{data: tree name}` |
| `get_parameter_tree` | GET `BASE/tree/{name}` | No body | 200 `{data: recursive node}` |
| `put_parameter_node` | PUT `BASE/tree/{tree}/{relative path}` | `ParameterNodeWrite`, aliased JSON | 201 `{data: node}` |
| `delete_parameter_tree` | DELETE `BASE/tree/{name}` | No body | 200 `{data: 'ok'}` |
| `delete_parameter_node` | DELETE `BASE/tree/{tree}/{relative path}` | `ParameterNodeDelete`, aliased JSON | 200 `{data: 'ok'}` |
| `list_parameter_blobs` | GET `BASE/treeblobs` | No body; repeated `treeNames` from query model | 200 `{data: {isComplete, blobRefs}}` |
| `prepare_parameter_upload` | PUT `BASE/binaryfilenode/{tree}/{relative path}` | No body; metadata projected to required headers | 201 `{data: FileNode with blobRefId and optional uploadUrl}` |
| `commit_parameter_upload` | PATCH `BASE/binaryfilenode/{tree}/blobref/{id}` | No body; authentication/context only | 200 `{data: {upload: true}}` |

Root creation ignores the old SDK's redundant `{type:'ValueNode'}` body; a bodyless call follows the server operation. Request/query/header models use runtime validation and aliases. Do not send JSON `null` for bodyless operations. Use HTTPX `.request('DELETE', ..., json=...)` for the child deletion body; `.delete()` does not provide that JSON convenience argument.

### Routing and concurrency validation

- Tree name matches `^[0-9A-Za-z][0-9A-Za-z._-]{0,49}$`.
- A child `tree_path` contains a valid tree name and at least one nonempty path component. Reject absolute paths, traversal components `.`/`..`, backslashes, and empty internal components; do not silently clean or rename input.
- Percent-encode individual components when constructing request URLs, retaining the separator structure. The service's node validation still applies after decoding.
- The reference child path validator, applied after the server's type-aware slash normalization, is `^/([0-9A-Za-z][0-9A-Za-z._-]{0,49}/)*[0-9A-Za-z][0-9A-Za-z._-]{0,49}(/|\.[0-9A-Za-z.]+)?$`. Helpers preflight known restrictions; low-level calls surface backend restrictions as errors. Hidden entries remain eligible for inspection, but unsupported names cannot be uploaded successfully without renaming, which is outside scope.
- `blob_ref_id` is a nonzero decimal string in node and completion contracts. Convert to integer only for matching numeric IDs in blob lists, without changing the node wire schema.
- `version=0` is create-only. Existing child updates/deletions use the version from `get_parameter_tree().data`. Methods never fetch or refresh versions automatically.

### Failure contract

Preserve existing SDK mappings for HTTP errors, including 400/403 → `MethodNotAllowedError`, 401 → `UnauthorizedAccessError`, 404 → `HttpNotFoundError`, and 409 → `HttpAlreadyExistsError`. Other established mappings remain unchanged. Transport failures stay HTTPX exceptions; request/response schema failures stay Pydantic errors. A private v1 response checker rejects non-2xx statuses, malformed JSON, null payloads, and error envelopes presented as successful responses. Unexpected redirects must not be interpreted as acknowledgments.

Do not change the global error taxonomy for this feature. The checker should use existing error handling for standard `{error:string}` bodies and tolerate unexpected error-body shapes without producing incidental attribute errors. No error result is returned as a successful model.

## Public helpers

Exports:

```text
rapyuta_io_sdk_v2.helpers.upload_parameters
rapyuta_io_sdk_v2.helpers.upload_parameters_async
```

```text
upload_parameters(client: Client, rootdir: str | Path, *,
                  options: ParameterUploadOptions | None = None,
                  storage_client: httpx.Client | None = None) -> ParameterUploadResult

async upload_parameters_async(client: AsyncClient, rootdir: str | Path, *,
                              options: ParameterUploadOptions | None = None,
                              storage_client: httpx.AsyncClient | None = None)
                              -> ParameterUploadResult
```

Each accepts at most four arguments and shares the model contract. Options default to all trees, no recreation, and folder mode. An injected storage client must be unauthenticated, have no platform context/cookies, and not follow redirects; reject an unsafe injected configuration before mutations. Callers own injected clients; helpers own and close any storage client they create. Supplied platform clients stay open.

### Selection and traversal

1. Validate options, source accessibility, auth/project/core configuration, immediate child selection, eligible entry metadata/readability, backend path restrictions, and maximum file size before any tree mutation. Inspect symlinks with `lstat`; never traverse them. Metadata preflight does not retain all file bytes or promise atomic snapshots.
2. Empty or omitted selection means all eligible child tree directories. Match nonempty selection exactly; report unmatched names when some match and fail if none match. Record loose root files as skipped. An empty source returns a no-op result.
3. Process sorted selected trees sequentially. With recreation, delete a selected tree first; tolerate only its actual idempotent absent result. Stop on deletion errors. Create a fresh value-node root. Without recreation, create the root directly; if it already exists, report the reference's conflict and retain existing content.
4. Create parent directories before children. Folder mode uses folder descendants. Legacy mode uses attribute at depth one, value at depth two, and alternates thereafter; files directly inside attribute directories are skipped and recorded. Legacy directory nodes cannot have extensions or repeat an attribute name along a branch; validate these restrictions before recreation. Folder paths are validated after adding the service's trailing directory slash.
5. Process eligible files once in both modes. Raw size above 131072 bytes or an extension other than `.yaml`/`.json` routes directly to a blob without parsing. At or below that raw threshold, decode UTF-8 without newline rewriting and validate YAML as a mapping or JSON as valid JSON before checking `len(json.dumps(payload)) + 200 > 131072` with the reference payload shape/escaping. Invalid candidates fail even if escaping would push their stored representation above the limit; valid candidates exceeding that estimate use blob storage. Eligible blob files above 209715200000 bytes fail preflight before any remote mutation.
6. Recheck source identities on open and after reads/transfers. A changed/disappeared source fails; do not confirm a binary file whose transfer source changed.
7. Add a tree to completed results only after all its eligible content finishes. Return the immutable result after all selected trees complete.

### Deduplication and completion

A prepare response with ID but no URL requires `list_parameter_blobs(ParameterBlobQuery(tree_names=(tree_name,)))` and a matching ID/checksum with status `Uploaded`. Missing ID or a non-uploaded matching reference fails. The result records every intended path even when content is shared.

After storage succeeds, call `commit_parameter_upload`. Only the known 403 duplicate lifecycle error may trigger a blob-list verification. If the matching reference is Uploaded with the expected checksum, record completion; if not, or verification fails, retain the original completion failure and any verification context. Individual client methods never suppress these errors or perform the status query themselves.

### Outcomes and failures

Helpers raise `ParameterUploadError` on ordinary failures, with `.failure.path`, `.failure.stage`, and `.partial_result`. Its exception cause preserves the original error. Preflight failure has no remote progress; later failure can contain deleted trees, created directories, and completed files even when no tree has fully completed. Results never count prepared-only or transferred-but-unconfirmed files as completed.

Async cancellation raises `ParameterUploadCancelled` from the original cancellation. This public exception subclasses `asyncio.CancelledError` and exposes `.failure: ParameterUploadFailure` and `.partial_result: ParameterUploadResult`, preserving cancellation semantics while identifying the last path/stage, completed item identities, skipped entries, and known deletions/directories. Safe notes may supplement these fields. The helper stops future scheduling and releases owned resources. An already issued remote operation may have taken effect without acknowledgment and is not counted as confirmed completion. No automatic rollback, resume, retry, or whole-submission atomicity is offered.

`ParameterUploadError` and `ParameterUploadCancelled` are imported from `rapyuta_io_sdk_v2.exceptions`; they are exceptions, not platform payload models.

## Compatibility acceptance

The mandatory `tests/reference/test_parameter_compatibility.py` gate installs the pinned reference SDK in a test-only environment, runs each new helper against isolated transports, then passes the resulting stored trees and blob content to the SDK v1 public `Client.download_configurations` through mocked HTTP requests. It must execute the real reference downloader, fail on unexpected network attempts, and compare source/restored eligible paths, empty folders, inline text, and blob bytes/checksums for folder and legacy fixtures. Cover selection, stored-size boundaries, multi-block files, and duplicate-content references through both client modes. The reference CLI delegates to this same downloader; no copied reconstruction function can substitute for the gate. All required reference cases must execute with zero skipped cases. Gate hooks in `tests/reference/conftest.py` must return a failing pytest exit status if no reference cases execute or any required reference case is skipped, even when pytest would ordinarily treat skips as success. Missing reference tooling or wrong package provenance also fails the gate. Live CLI/SDK checks provide separately reported supplemental evidence.

## Scope exclusions

No device apply methods, high-level download/diff workflow, raw filenode upload convenience method, migration to v2 ConfigTree, or CLI command is added. Existing v2 ConfigTree and authentication behavior must continue to pass regression tests.
