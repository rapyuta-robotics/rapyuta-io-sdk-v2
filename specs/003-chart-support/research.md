# Research: Chart Support

All planning unknowns are resolved. Findings come from the SDK, the specified rio CLI checkout, the existing parity fixtures, and primary Python/HTTPX documentation. Research was split between acquisition/cancellation and wrapper/lifecycle contracts. No platform operations were performed.

## 1. Compose prepared Appliers

**Decision**: Introduce `Chart` and `AsyncChart` in a separate `rapyuta_io_sdk_v2/chart/` package. Explicit `load` factories obtain and validate sources and construct one existing `Applier` or `AsyncApplier`. Ordinary lifecycle methods return `ApplierResult`, inspection returns `InspectionResult`, and resource exceptions propagate unchanged.

**Rationale**: `apply/applier.py` eagerly prepares the collection and `_for_scope` copies its base for every execution. It already supplies scope isolation, cancellation settlement, client ownership, and structured progress. The loader accepts individual files, so Chart discovers and orders files before creating `ManifestSource`. No client, scheduler, resource, renderer, or platform payload changes are needed.

**Alternatives considered**: Subclassing Applier couples packaging to its private internals. Reimplementing rendering or lifecycle duplicates established behavior. Rebuilding resource models from inspection loses original pre-model documents. Implicit constructor downloads hide I/O from async callers.

## 2. Source and input configuration

**Decision**: Use a frozen tagged `ChartSource` with directory, archive, and repository factories. Aggregate rendering arguments in a frozen `ChartInputs` dataclass whose typed constructor accepts values, secrets, rio context, and an interface resolver. Normalize and deep-copy these inputs through existing `ManifestSource` behavior. Pass `ApplierOptions` separately, with existing defaults.

**Rationale**: A nonexistent path must not be guessed to be a repository chart. Aggregation keeps the load signature within configured Ruff argument limits and preserves an explicit empty values mapping as one supplied source. If the normalized values sequence is empty, supply bundled `values.yaml`; otherwise never inject defaults. Caller-supplied values and secrets paths may be outside the chart root.

**Alternatives considered**: A string accepting either a path or name is ambiguous. Many convenience load variants duplicate contracts. Truthiness of a values mapping incorrectly treats `{}` as absent. Layering defaults underneath explicit inputs contradicts CLI behavior.

## 3. CLI repository and branch semantics

**Decision**: Preserve `DEFAULT_REPOSITORY`, `BRANCH_REPO_BASE`, and `branch_repository_url(branch)` with the CLI's `quote(branch, safe="/")` behavior. Add sync/async repository helpers for index retrieval, exact-name/version lookup, and stable case-insensitive name listing. Non-empty branch selection overrides a supplied index; empty branch uses the supplied index or the default. Exact version returns the first match; unversioned lookup returns all versions in index order; loading selects the first and issues `ChartVersionWarning` if several match. Download only the selected entry's first URL.

**Rationale**: The reference `riocli/chart/util.py` and chart commands define these observable decisions. Its branch unit tests cover slashes, spaces, query characters, and Unicode. Selecting a semantic latest version or rejecting unversioned ambiguity would diverge from the clarified requirement.

**Alternatives considered**: Sort versions, fall back to another package URL, silently fall back from a branch, or require an exact version. All change the CLI's decisions. CLI table formatting, spinners, authentication, and accidental error shapes remain outside the SDK contract.

## 4. Acquisition transport ownership

**Decision**: Use existing HTTPX dependency with native sync/async requests and redirects enabled. An owned HTTPX client lives for one index-plus-package load or one repository method call, using a finite 30-second HTTPX timeout. Permit an optional caller-owned matching HTTPX client for private sources and `MockTransport` tests; preserve its timeout configuration and leave it open. Never reuse a platform client's transport. No retry or persistent cache is introduced.

**Rationale**: HTTPX already provides both transports and deterministic mock transport. Explicit redirects preserve Requests' default GET behavior in the CLI. HTTPX's timeout covers connect/read/write/pool inactivity, not a guaranteed total operation deadline. Prepared Chart lifetime is independent of acquisition transport lifetime. Sources: [HTTPX API](https://www.python-httpx.org/api/), [async support](https://www.python-httpx.org/async/), [timeouts](https://www.python-httpx.org/advanced/timeouts/), [transports](https://www.python-httpx.org/advanced/transports/).

**Alternatives considered**: Add Requests, use sync HTTP in a worker, or borrow an authenticated platform transport. These add dependencies, weaken request cancellation, or couple credentials and unrelated lifetimes. Custom retry/timeout option hierarchies add no required behavior; callers can supply an HTTPX client.

## 5. Filesystem validation and eager cleanup

**Decision**: Load compressed tar charts inside an owned `TemporaryDirectory`. Validate every member before extraction, allow only ordinary files/directories, and explicitly apply `tarfile.data_filter`. Reject absolute paths, parent traversal, foreign separators, links, special files, duplicate destinations, and file/directory collisions. Accept one chart at archive root or one top-level chart directory; reject ambiguous roots. Validate local descendants without following symlinks or special files. Check metadata identity against a selected repository entry.

**Rationale**: Python 3.13 extraction defaults must not determine security behavior. Python recommends private extraction destinations and checks beyond its filter. Ordinary local sources stay caller-owned. Chart discovery recursively selects `.yaml`, `.yml`, and `.json` templates in relative POSIX path order. The Applier stores complete prepared data, allowing extracted files to disappear before load returns. Sources: [Python 3.13 tarfile extraction filters](https://docs.python.org/3.13/library/tarfile.html#extraction-filters), [temporary directories](https://docs.python.org/3.13/library/tempfile.html#tempfile.TemporaryDirectory).

**Alternatives considered**: Unfiltered `extractall`, skipped invalid members, archive overwrite order, or files retained for the Chart lifetime. These permit unsafe or ambiguous input and unnecessary close obligations. Size quotas, digest enforcement, and sandboxing adversarial mutation of a caller's local directory are outside this specified release.

## 6. Native async acquisition and settled local work

**Decision**: Use native asynchronous HTTP for index/package acquisition. Offload blocking filesystem work, archive validation/extraction, YAML index parsing, and `AsyncApplier` construction/rendering using tracked `asyncio.to_thread` tasks. The existing synchronous interface resolver therefore executes on the preparation worker thread; callers provide thread-safe resolution or prefetched data. Shield these tasks, and on cancellation join them before propagating the original cancellation. Settlement tolerates repeated cancellation and consumes worker exceptions. Temporary-directory ownership belongs to the worker's lexical scope; cleanup completes before the worker finishes. Settle owned async transport closure similarly.

**Rationale**: Cancelling an executor future cannot stop a running thread. Directly awaiting `to_thread` could return cancellation while extraction or rendering still uses files. The existing Apply scheduler demonstrates shielded settlement, but Chart should own its own small acquisition settlement helper rather than import scheduler internals. Sources: [asyncio running in threads and shielding](https://docs.python.org/3.13/library/asyncio-task.html#running-in-threads), [executor cancellation](https://docs.python.org/3.13/library/concurrent.futures.html#concurrent.futures.Future.cancel).

**Alternatives considered**: Block the event loop, cancel a running preparation task, detach a background download, or remove files before its worker settles. Each violates continued application progress or the no-background-work-after-return requirement. Waiting for a caller's resolver to finish can delay cancellation; callbacks are required to terminate and remain caller-controlled.

## 7. Recreation and partial progress

**Decision**: `apply(delete_existing=True)` delegates delete then apply to the same prepared Applier under one nonblocking Chart lock. Return the final apply `ApplierResult`. Expose `phase_results: tuple[ApplierResult, ...]` for settled phases in the current call and delegate `last_result`. Reset phase results only after acquiring the operation guard. Capture a phase's result in `finally` only if delegate `last_result` differs by object identity from its value before that phase.

**Rationale**: Delegate preparation is reused while per-call execution state is fresh. Existing delegate locks leave a gap between recreation phases. A preflight failure can leave `last_result` unchanged, so blindly appending it would misattribute a previous call's result. Preserve execution exceptions and `CancelledError`; a failed/cancelled delete never enters apply. Both dry-run phases use existing previews.

**Alternatives considered**: Return a new composite lifecycle result, wrap existing errors, or reconstruct an Applier for every phase. None is needed to preserve both phase snapshots and the existing return contract.

## 8. Diagnostics and compatibility verification

**Decision**: Add chart load errors for source/index/download/archive/metadata stages, with original source and stable category fields. Preserve Apply preparation errors, resource errors, and cancellation, adding chart origin and chart-relative path context through exception notes when needed. Return independent metadata snapshots. Keep a private mapping of staging paths to relative chart paths for diagnostics.

**Rationale**: Extracted files no longer exist after preparation, but callers still need a useful original source and relative template name. Existing `SourceLocation` and rendered documents remain unchanged. No raw HTTP response bodies or runtime transport objects belong in result models.

**Alternatives considered**: Rewrite Apply errors/results or retain staged files solely for diagnostics. These change existing contracts or impose unnecessary lifetime management.

**Verification decision**: Extend controlled CLI-oracle capture with a separate chart-workflow suite, preserving existing suites and fixtures. Patch acquisition and callbacks to capture Chart forwarding; separately execute the real Apply callback with underlying Applier/configuration/presentation boundaries controlled to capture recreation phase order and deletion-failure short-circuiting. Recreation orchestration lives in that callback, so replacing it is insufficient evidence. Record revisions and inputs. Normal tests read checked-in expected selection, URL, callback-phase, and manifest output without importing rio. Stage chart roots around existing six fixture cases; their source sets lack `Chart.yaml`, and postgis uses `values.sample.yaml`, so fixture staging supplies recorded metadata and copies the base to `values.yaml` without rewriting established references. Verify zero account access and no automatic platform mutations.
