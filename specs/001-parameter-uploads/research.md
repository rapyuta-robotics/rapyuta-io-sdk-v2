# Research: Parameter Uploads

Date: 2026-10-13. All planning unknowns below are resolved. No live platform mutations or storage uploads were performed.

## Evidence and initial gates

The initial constitution review passed: extend the existing Python package, give each client method one operation and a Pydantic contract, and put orchestration in separate helpers. The design must meet current Python and Ruff requirements without copying legacy implementation weaknesses.

Two read-only research agents examined service contracts and transfer design. Source evidence:

- SDK v1 revision `739a6fe44600ff0964fa56b04878ddb21e76b5be`: `/home/ankit/Projects/Work/rapyuta-io-sdk/rapyuta_io/clients/paramserver.py`, `utils/settings.py`, `utils/utils.py`, `utils/storage.py`, and `tests/paramserver_test.py`.
- CLI revision `27bb77bb912705b58a5de0a2e99848dc023ba322`: `/home/ankit/Projects/Work/rapyuta-io-cli/riocli/parameter/{upload,utils}.py`, `riocli/auth/staging.py`, and Parameter tests.
- Service revision `4338812cda3502f7a2332bd6c6093fc491d179c2`, branch `devel`: `/home/ankit/Projects/Work/rapyuta_io/pkg/paramserver/{controller,api,node,http,apihelpers}.go`, `kodagu/node/{node,tree}.go`, `kodagu/store/{put,delete}.go`, and `pkg/blobservice/{api.go,models/models.go}`.
- Current SDK: `rapyuta_io_sdk_v2/{client,async_client,config,utils,exceptions,_client_options}.py`, model conventions, `pyproject.toml`, and existing test fixtures.

The service source corroborates wire shapes consumed by SDK v1. It is source evidence, not a guarantee about every deployed environment; implementation must include fixtures reflecting these contracts and a mandatory isolated round-trip through the actual reference SDK downloader. Live validation is supplemental and is reported separately when a disposable project is available.

## 1. Parameter operation boundaries

**Decision**: Expose nine client methods across the spec's seven operation categories. Separate root creation/deletion from child PUT/DELETE; read a complete tree containing recursive nodes. Use the core service's `/api/paramserver` routes.

**Rationale**: The server has no child-node GET route. Root creation returns a tree-name string and ignores a node body, while child creation returns a node. Child deletion parses a JSON request containing node version/type, unlike root deletion. Splitting these operations preserves precise contracts.

**Alternatives considered**: A generic tree-path method with a union response obscures root/child differences. Adding a nested GET endpoint would invent a service capability. Convenience node lookup can be built separately later.

The spec was corrected to describe recursive reads, version-aware child deletion, and platform validation of unsupported names. This is an evidence-based contract correction, not an added feature.

## 2. Models, envelopes, and optimistic versions

**Decision**: Add operation-specific models in `models/parameter.py`, inheriting `SDKModel`. Successful envelopes require `data`; tree lists use arrays, root creation uses a string, node reads/writes use recursive nodes, deletion uses `"ok"`, and completion uses `{upload:true}`. Reject literal null, missing data, and malformed shapes. Use aliases for every non-snake-case wire field.

**Rationale**: `paramserver/http.go` sends `{data:...}` or `{error:...}` without a success flag. SDK tests returning literal `null` are lax mocks. `ListTrees` explicitly returns an empty array; treeblobs explicitly returns `blobRefs:[]`. Node versions are required for optimistic updates; `0` creates a new path, a stored version updates it. Tree creation can fail when the tree already exists, so the helper must expose that failure unless recreation is selected.

**Alternatives considered**: Reusing v2 `ConfigTree` or `APIResponse` would misrepresent the wire contract. Raw dictionaries and silently defaulted acknowledgments violate the constitution. Automatically fetching versions and merging existing trees would introduce an unrequested workflow.

Use validated model serialization with aliases and `exclude_unset=True`; preserve explicit supported values. Pydantic documents [nested models and validation](https://docs.pydantic.dev/latest/concepts/models/) and [field serialization controls](https://docs.pydantic.dev/latest/concepts/serialization/). Header/query payloads also have named models, even when a request has no JSON body.

## 3. Core service configuration

**Decision**: Append `core_api_host` to `Configuration`, publish `hosts['core_api_host']`, and read it from config files. Production defaults to `https://gaapiserver.apps.okd4v2.prod.rapyuta.io`; staging uses `https://{environment}apiserver.apps.okd4v2.okd4beta.rapyuta.io`. Local requires an explicit override or `LOCAL_COREAPI_HOST`; without it only Parameter operations raise a configuration error.

**Rationale**: These production/staging values match reference sources. The v2 API host is a different gateway. No authoritative local core default was found, so do not guess one or send local requests to production. Parameter methods read the resolved slot at call time so environment changes take effect.

**Alternatives considered**: Appending `/api/paramserver` to `v2api_host` without evidence, globally requiring a core endpoint at SDK construction, or inventing a local default would risk incorrect routing or break existing callers. Append the new dataclass field to preserve existing positional construction.

## 4. Source selection, traversal, and file classification

**Decision**: Default to folder mode; expose legacy mode through `ParameterUploadOptions.as_folder=False`. Select immediate child directories by exact name. Preflight records only entry metadata, not all file contents, then process selected trees sequentially in sorted parent-first order.

**Rationale**: CLI upload passes `as_folder=True`. Legacy mode alternates value/attribute directories and ignores attribute-level files. A metadata manifest supports readable-source validation, partial reporting, and file-change checks before recreation begins. Use `lstat`, skip links/special entries, and revalidate entry and ancestor identities on open; do not traverse links.

**Alternatives considered**: Recursive thread pools copy race and reporting complexity from SDK v1. Lazy creation before source validation could delete a tree despite an invalid source. Holding every file's bytes would violate the feature's memory requirement.

Classification is applied once in both modes: raw size above 131072 bytes uses a blob; otherwise only `.yaml` and `.json` are candidates for inline storage. Decode UTF-8 without newline normalization, validate YAML as a mapping or JSON as valid JSON, preserve the original text, then use `len(json.dumps({'type':'FileNode','data':text,'contentType':mime})) + 200 > 131072` to choose blobs. Preserve default escaping/separators for this reference estimate. This fixes legacy SDK double scheduling without changing intended file routing. Validation occurs before the stored-size decision for structured candidates at or below the raw threshold, including malformed text whose escaped representation would otherwise exceed the limit; only direct blob routes bypass parsing.

The implementation audit also verified `kodagu/node/node.go` rejects extensions on legacy directory nodes and duplicate attribute names along a branch; `sanitizeRelPath` adds a trailing slash to folder nodes before the path regex. Preflight enforces these known constraints before recreation.

Known server path restrictions are documented in contracts. Encode segments literally, reject traversal segments, and surface unsupported paths without renaming. Hidden entries are inspected normally but can still fail platform name validation.

## 5. Authorization and deduplication

**Decision**: Treat upload preparation as a typed node response requiring a nonzero decimal string blob ID. An upload URL initiates transfer. If no URL is present, confirm the same ID and checksum have status `Uploaded` through the public treeblobs operation before recording success.

**Rationale**: Uploaded content retains its ID but omits the URL; incomplete content gets an upload URL (`apihelpers.go`). Missing an ID is malformed. The real HTTP 403 completion message combines an invalid lifecycle with an already uploaded blob, so text alone cannot establish success.

**Alternatives considered**: SDK v1 suppresses missing authorization fields and two message substrings. Copying this behavior can lose content or hide a failure. Rejecting every duplicate completion would fail legitimate concurrent content reuse.

On the known completion HTTP 403, the helper may read treeblobs and accept only the same ID with `Uploaded` status and matching checksum. Other errors propagate. Individual client methods always expose operation errors; only helpers combine confirmation with a status query.

## 6. Blob transfer without a new runtime dependency

**Decision**: Use a dedicated unauthenticated HTTPX storage adapter. Files up to 4 MiB, including empty files, use Put Blob. Larger files use sequential 4 MiB blocks and Put Block List. Reject more than 50000 blocks during local preflight (maximum supported file size 209715200000 bytes, about 195.3 GiB).

**Rationale**: Existing HTTPX supports both client modes. REST transfers avoid an Azure runtime dependency while retaining byte integrity and media metadata. Fixed blocks give bounded memory and a straightforward tested transfer protocol. The documented size bound far exceeds reference configuration fixtures but remains an explicit SDK constraint.

**Alternatives considered**: A single PUT for every file can exceed service limits. Azure's SDK adds dependencies and separate async integration. Adaptive multi-gigabyte blocks and concurrent transfers add complexity beyond configuration uploads.

REST details: send Base64 MD5 values to storage, distinct from hexadecimal platform `Checksum`. Put Blob uses `x-ms-blob-type: BlockBlob`, explicit length, and file content settings. Each staged block carries its own `Content-MD5`; final block-list commit persists the full-file MD5 and media settings. A block-list content MD5 is a property, not assembled-file validation, so compare an incremental second local hash before committing. Preserve the SAS query and append encoded operation parameters; use unique fixed-length attempt IDs and block indices. These decisions follow [Put Blob](https://learn.microsoft.com/en-us/rest/api/storageservices/put-blob), [Put Block](https://learn.microsoft.com/en-us/rest/api/storageservices/put-block), and [Put Block List](https://learn.microsoft.com/en-us/rest/api/storageservices/put-block-list).

## 7. Async work, resource ownership, and failures

**Decision**: Network calls use the supplied client's async transport and an async storage client. Disk scans, reads, and checksums use `asyncio.to_thread`; disk workers own file handles so cancellation cannot close a handle still being used by another thread. No background upload tasks or automatic retries.

**Rationale**: Sequential awaitable I/O satisfies responsiveness without unbounded workers. Separate storage clients prevent platform authorization, project headers, cookies, or HTTP auth from entering signed-URL requests. Close owned clients after each submission; injected platform/storage clients remain caller-owned.

**Alternatives considered**: Running synchronous network calls in an executor would obscure async resource and cancellation behavior. Reusing platform transport for storage can leak credentials. Automatic rollback/retry does not belong in this feature.

HTTPX describes [async request bodies and client lifetime](https://www.python-httpx.org/async/); Python describes [thread offloading](https://docs.python.org/3.13/library/asyncio-task.html#asyncio.to_thread). Offloaded work is not forcibly stopped by task cancellation; each worker must finish and clean up its own handle.

Ordinary failures raise `ParameterUploadError` with a typed partial result and failure context, chaining the original exception. Cancellation raises `ParameterUploadCancelled`, a subclass of `CancelledError`, from the original cancellation with typed `.failure` and immutable `.partial_result` fields containing the known item identities, skips, and partial remote progress. Notes are optional additions, not the result contract. It never triggers later confirmation or rollback. Local source-change checks use stat identity and both upload-pass hashes; they detect changes without claiming atomic filesystem snapshots.

## 8. Repository integration and verification

**Decision**: Add source-backed serialization/validation tests and sync/async request parity; helper tests use temporary sources and separate storage MockTransport. Exercise exact bytes, checksums, query preservation, cancellation, dedup, replacement, and failures. Add a required isolated round-trip through the actual SDK v1 public downloader using captured helper-produced tree/blob state. Keep existing ConfigTree regression tests and required Ruff checks.

Use a test-only `reference` dependency group for `rapyuta-io` pinned to SDK revision `739a6fe44600ff0964fa56b04878ddb21e76b5be`, leaving package runtime dependencies unchanged. The compatibility test blocks unhandled requests and requires every case to run, without skip fallbacks or live credentials. The inspected CLI download command delegates to this SDK downloader. Installing both inspected packages into the same environment is not required: the inspected CLI declares `rapyuta_io>=3.1.0`, while the pinned SDK checkout declares version `3.0.0`. This avoids an unsatisfiable reference dependency combination while exercising the actual shared data-consumer contract.

**Rationale**: Existing tests already use HTTPX responses and pytest-asyncio. The current error handler maps 400/403 to `MethodNotAllowedError` and 401 to `UnauthorizedAccessError`; preserve those established types while attaching Parameter path/stage in helpers. Validate v1 envelopes independently and reject unexpected redirects. New async Parameter methods must never use `AsyncClient.sync_client`; existing synchronous identity methods in that class are pre-existing noncompliance and are outside this change.

**Alternatives considered**: Porting lax legacy mocks, testing only happy paths, or rewriting all SDK error mappings would miss compatibility hazards or broaden scope. No test suite was run for this documentation-only planning change.

## Resolved constraints

No unresolved design questions remain. Local Parameter endpoint setup is an explicit configuration requirement. Service revisions are pinned as evidence. The isolated reference downloader gate is required for implementation acceptance and cannot be replaced by an unavailable-live-check note; supplemental live checks remain separately reported. No implementation verification is claimed at planning time.
