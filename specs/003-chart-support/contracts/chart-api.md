# Public Chart API Contract

This is the proposed public library interface for implementation. Import Chart types from `rapyuta_io_sdk_v2` or `rapyuta_io_sdk_v2.chart`; chart Pydantic models are also exported by `rapyuta_io_sdk_v2.models`. Existing Apply types and exceptions retain their current imports.

## Source Selection

```python
ChartSource.from_directory(path: str | Path) -> ChartSource
ChartSource.from_archive(path: str | Path) -> ChartSource
ChartSource.from_repository(
    selector: str, *, repository: str | None = None, branch: str | None = None
) -> ChartSource
```

Factories are free of I/O and validate the tag/fields and selector. A source is interpreted only by its tag, never by guessing whether a string exists on disk. Invalid configuration raises Pydantic validation errors; load boundary errors follow the chart error contract. Repository index and first package URL support absolute HTTP(S), not implicit file URLs or relative URL resolution.

## Render Inputs and Loading

```python
ChartInputs(
    *,
    values: ValueInput | Iterable[ValueInput] | None = (),
    secrets: ValueInput | Iterable[ValueInput] | None = (),
    rio: Mapping[str, JsonValue] | None = None,
    interface_resolver: DeviceInterfaceResolver | None = None,
)

Chart.load(
    source: ChartSource,
    *,
    inputs: ChartInputs | None = None,
    options: ApplierOptions | None = None,
    http_client: httpx.Client | None = None,
) -> Chart

async AsyncChart.load(
    source: ChartSource,
    *,
    inputs: ChartInputs | None = None,
    options: ApplierOptions | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> AsyncChart
```

Signature blocks describe interfaces rather than implementation bodies. Loading produces a fully prepared facade; direct constructors are internal and perform no I/O. No platform client is accepted while loading. `options=None` uses existing Applier defaults: workers six, readiness 50 checks at six-second intervals, and empty explicit scope.

No normalized values sources means bundled `values.yaml`; any explicit source replaces bundled defaults. `{}` is an explicit source. Mappings and ordered plain YAML/JSON files match `ManifestSource` inputs. Caller values/secrets paths may reside outside the chart root. Users explicitly call the existing decryption helper before supplying encrypted secret values. Chart does not discover CLI configuration, authenticate, or resolve missing device context.

Local loading uses no acquisition HTTP client. Owned network clients use redirects and a 30-second HTTPX inactivity timeout; a supplied HTTPX client supplies its own timeout policy and remains open. The helper passes redirect behavior explicitly without mutating supplied configuration. Wrong HTTPX execution mode is a usage error before requests. The platform `Client` and `AsyncClient` are never accepted as acquisition clients.

Synchronous loading and lifecycle execution reject use inside an active event loop before blocking work with `ApplierUsageError` directing callers to AsyncChart. `AsyncChart.load` is awaitable for every source kind; native async network and tracked offloaded preparation let other tasks progress. Its synchronous `DeviceInterfaceResolver`, when used by rendering, executes on the preparation worker thread, so the caller must provide a thread-safe callable or prefetched snapshot rather than an event-loop-affine callback. Cancellation waits for started preparation and owned cleanup before propagating the original `CancelledError`.

After load returns, the facade retains no owned transport or extracted files. It needs no `close()` method or context manager, and source files are not reread for later operations. Local source edits after load do not alter prepared manifests. Load again to use changed chart contents or values.

## Inspection and Properties

```python
chart.metadata -> ChartMetadata
chart.entry -> ChartEntry | None
chart.source -> ChartSource
chart.template_paths -> tuple[str, ...]
chart.options -> ApplierOptions
chart.last_result -> ApplierResult | None
chart.phase_results -> tuple[ApplierResult, ...]
chart.inspect() -> InspectionResult
```

Both Chart variants expose synchronous read-only inspection because preparation has already finished and no I/O is needed. Metadata, selected entry, and inspection results are independent copies. Template paths are chart-root-relative POSIX names; source identifies the caller's original path/reference. Existing `SourceLocation` fields remain unchanged; errors associated with staged paths gain original chart source and relative template context through notes where needed.

## Lifecycle Methods

```python
Chart.apply(
    client: Client | None = None,
    *, dry_run: bool = False, delete_existing: bool = False,
) -> ApplierResult
Chart.delete(client: Client | None = None, *, dry_run: bool = False) -> ApplierResult

async AsyncChart.apply(
    client: AsyncClient | None = None,
    *, dry_run: bool = False, delete_existing: bool = False,
) -> ApplierResult
async AsyncChart.delete(
    client: AsyncClient | None = None, *, dry_run: bool = False,
) -> ApplierResult
```

Pass the exact compatible configured SDK client only at live execution time. Empty collections, missing client/context, wrong execution mode, resource capability validation, retention, dependency order, readiness, uncertain writes, failures, and cancellation follow direct Applier contracts. Clients remain caller-owned and are neither closed, replaced, configured, nor retained between calls.

`dry_run=True` requires no client and makes no platform requests; planned outcomes never imply completed writes. Inspection and dry-run have no repository I/O after load. Repository access needed to obtain a remote chart occurs during explicit loading.

The wrapper delegates lifecycle work rather than re-rendering templates or implementing resource operations. Repeated calls use fresh execution state from the internal Applier while retaining the same prepared inputs. Different compatible clients may supply different routing scope sequentially, subject to existing explicit-scope conflict checks.

## Recreation, Guarding, and Phase Progress

With `delete_existing=True`, apply runs delete and then apply using the same prepared collection and settings. Successful invocation returns the apply phase's `ApplierResult`; the deletion result remains available in `phase_results`. Preview likewise records planned delete and apply phases.

One nonblocking wrapper operation guard spans the entire lifecycle call, including the gap between recreation phases. Rejected concurrent calls raise `ApplierUsageError` without resetting or changing the active call's phase snapshots. After acquiring the guard, the accepted call resets `phase_results`; each settled delegated phase adds its newly published result in `finally`. Compare the delegate's result object before/after the phase so preflight rejection cannot attribute an old result to the new call. The guard is released on success, failure, and cancellation.

| Outcome | Return/exception | `phase_results` |
| --- | --- | --- |
| Ordinary success or preview | Original ApplierResult | One new result. |
| Ordinary execution failure/cancellation after settlement | Original error/cancellation | New settled failure/cancellation result when published. |
| Recreation succeeds | Original apply result | Delete, then apply. |
| Delete execution fails/cancels | Original error/cancellation; apply never starts | Settled delete result when published. |
| Delete succeeds; apply execution fails/cancels | Original apply error/cancellation | Successful delete plus settled apply result when published. |
| Delete preflight is rejected | Original validation/usage error | Empty; no stale result appended. |
| Delete succeeds; apply preflight is rejected | Original validation/usage error | Successful delete only. |

`last_result` preserves the delegate's established latest-settled-result behavior. It is not cleared on rejected preflight. Errors are not wrapped in a new recreation error type; callers combine the original error's result and `phase_results`. No rollback is performed or claimed.

## Repository Helpers

```python
ChartRepository(
    repository: str | None = None,
    *, branch: str | None = None, http_client: httpx.Client | None = None,
)
AsyncChartRepository(
    repository: str | None = None,
    *, branch: str | None = None, http_client: httpx.AsyncClient | None = None,
)

repository.index_url -> str
repository.fetch_index() -> ChartIndex
repository.find_chart(selector: str) -> tuple[ChartEntry, ...]
repository.list_charts() -> tuple[ChartEntry, ...]
```

The AsyncChartRepository equivalents of the three methods are awaitable; construction and `index_url` perform no I/O. `find_chart` also provides the metadata used by CLI info; no distinct presentation-oriented info/search API is necessary. There is no persistent cache or owned transport retained by a helper. Each method scopes its own client when none was supplied. Caller-supplied acquisition clients may be reused and are never closed. Returned data is independent of other returned objects.

Constants and pure function exported by `rapyuta_io_sdk_v2.chart`:

```python
DEFAULT_REPOSITORY = "https://rapyuta-robotics.github.io/rapyuta-charts/incubator/index.yaml"
BRANCH_REPO_BASE = "https://chartsbranch.blob.core.windows.net/charts-per-branch"
branch_repository_url(branch: str) -> str
```

Selection, fields, URL rules, and package validation are specified in [repository-format.md](repository-format.md). Validation uses [parity-validation.md](parity-validation.md).

## Error Boundaries

Chart source/index/download/archive/metadata failure raises `ChartLoadError`, exposing stage, category, source, and optional selector. Invalid explicit source configuration uses Pydantic validation; misuse of execution mode uses the existing `ApplierUsageError`. Preparation/render/dependency errors and resource execution errors remain existing Apply exceptions, with chart source notes when useful. Missing charts/versions, invalid first URLs, and bad metadata fail before platform operations. Unversioned loading with several entries emits `ChartVersionWarning`; returning all versions through `find_chart` does not warn.

No raw HTTP body, response object, decrypted values, or template contents are attached by chart acquisition errors. General Apply diagnostics retain the existing ordinary-data contract; Chart introduces no broader confidentiality guarantee for explicit render inputs.
