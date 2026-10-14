# Data Model: Chart Support

This is a library design. It introduces no database, migrations, platform resource kinds, or platform request/response changes.

## ChartSource

Frozen Pydantic `SDKModel` in `models/chart.py`, with tagged source selection and `extra="forbid"`.

| Field | Type | Meaning |
| --- | --- | --- |
| `kind` | `Literal["directory", "archive", "repository"]` | Explicit source interpretation. |
| `path` | `Path \| None` | Selected local directory/archive, resolved during load. |
| `selector` | `str \| None` | Repository `name` or `name:version`. |
| `repository` | `str \| None` | Optional absolute HTTP(S) index override. |
| `branch` | `str \| None` | Optional branch path; non-empty branch overrides the index. |

Directory/archive sources require a path and forbid repository fields. Repository sources require a non-empty selector and forbid a local path. Selector parsing preserves spelling and case, rejects more than one colon and empty name/version components, and does not infer a latest version. Factories `from_directory`, `from_archive`, and `from_repository` perform configuration validation without filesystem/network I/O. File existence and URL usability are checked at loading/retrieval boundaries.

## ChartInputs

Frozen runtime dataclass in `chart/source.py`, not a serialized API payload. Fields are normalized snapshots of the existing `ManifestSource` render inputs:

| Field | Normalized type | Rule |
| --- | --- | --- |
| `values` | `tuple[ValueInput, ...]` | Accept mapping/path singleton or ordered iterable; `{}` is one source. |
| `secrets` | `tuple[ValueInput, ...]` | Same accepted source forms; decryption is caller-explicit. |
| `rio` | `Mapping[str, JsonValue] \| None` | Deep-copied explicit reserved platform template context. |
| `interface_resolver` | `DeviceInterfaceResolver \| None` | Caller-owned callable retained without discovery or platform client injection. |

Constructor inputs use `ValueInput | Iterable[ValueInput] | None` for values/secrets. Normalize through `ManifestSource` rather than implementing new merging/validation. Snapshot input iterables once. Deep copies prevent changes to caller mappings from affecting loading; take independent copies when building the actual manifest source. Frozen dataclasses do not freeze every nested mapping: callers must not concurrently mutate the configuration object during a load.

An empty normalized values sequence means use chart-root `values.yaml`; a non-empty sequence excludes bundled defaults entirely. Default source parsing, recursive mapping merge, list/scalar replacement, JSON-value validation, and reserved namespaces belong to Applier. There is no new values schema or automatic SOPS operation.

## ChartMetadata

Frozen Pydantic `SDKModel` in `models/chart.py`.

| Field | Type | Rule |
| --- | --- | --- |
| `name` | `StrictStr` | Non-empty, not whitespace-only; spelling preserved. |
| `version` | `StrictStr` | Non-empty, not whitespace-only; opaque exact version string. |
| `description` | `str \| None` | Optional chart description. |
| `api_version` | `str \| None` | Alias `apiVersion`; preserve the package field. |
| Additional metadata | JSON-compatible extra fields | Preserve ordinary metadata such as maintainers/appVersion without changing global `SDKModel` configuration. |

Read `Chart.yaml` as exactly one safe YAML mapping. Reject missing/invalid metadata. For repository loading, package metadata name/version must equal the selected `ChartEntry`. Local sources use package-declared identity. Do not require repository fields in local metadata or invent release identities.

## ChartEntry and ChartIndex

`ChartEntry` extends chart metadata with `urls: tuple[str, ...] = ()`, optional `created: str | datetime | None`, and optional `digest: str | None`. Safe YAML can produce native timestamps; preserve their semantic value and use Pydantic JSON serialization for comparisons. Listing/lookup can expose entries without usable URLs; loading requires the first URL to be a usable absolute HTTP(S) location. The digest is metadata only; verification is not introduced because the reference does not enforce it.

`ChartIndex` is a frozen Pydantic model with required `entries: dict[str, tuple[ChartEntry, ...]]`, optional `api_version: str | None` (alias `apiVersion`), `generated: str | datetime | None`, and preserved JSON-compatible index metadata. Validate keys as non-empty chart names and entries as ordered sequences of typed models; declared entry name must agree with its key. Empty entries mapping is a valid empty catalog; finding a missing chart fails. Duplicate version entries preserve source order and first-match behavior. Preserve the spelling of metadata aliases.

Pydantic frozen configuration does not deeply freeze dictionaries or extras. Repository methods return fresh independent snapshots; mutating one returned index/entry must not affect another method result or a prepared chart's metadata.

## Prepared Chart / AsyncChart

Runtime facade in `chart/chart.py`, containing one matching prepared Applier, a source descriptor, metadata/selected-entry snapshots, options, chart-relative template paths, and private staging-path attribution. It contains no platform client, owned acquisition transport, or live temporary directory after loading.

Public data:

- `metadata: ChartMetadata` and `entry: ChartEntry | None` return independent copies.
- `source: ChartSource` exposes the original selection; `template_paths: tuple[str, ...]` lists selected paths relative to the chart root.
- `options: ApplierOptions` preserves the existing frozen execution settings.
- `last_result: ApplierResult | None` delegates the existing facade's most recent settled result.
- `phase_results: tuple[ApplierResult, ...]` contains only newly settled phases from the current/latest accepted lifecycle call.
- `inspect()` returns the existing independently copied `InspectionResult`, including pre-model documents and dependency data.

Construction/load state: `source selected → acquisition → structure validated → render/dependency preparation → prepared`. Failure/cancellation releases owned transport/files after settling active work, then propagates the appropriate error. Only a fully prepared facade is returned. No partially loaded Chart is exposed.

Operation state: `idle → guarded operation → delegated phase(s) → idle`. Recreation uses `delete → apply`, both on the same prepared delegate; the existing delegate creates fresh execution state per phase. Concurrent calls fail immediately without resetting the accepted operation's result snapshots. Read-only inspection does not create a platform operation.

## Operation Results

Reuse `ApplierResult`, `ResourceOutcome`, and `InspectionResult` unchanged. Ordinary apply/delete and their previews return one phase result. Recreation returns its final apply result and retains delete/apply results in `phase_results`, in execution order. Both successful and failed/cancelled settled phases are retained. A rejected preflight phase publishes no new result; it must not append a stale result from a previous call. `last_result` may still represent a previous settled call, exactly as with direct Applier use.

There is no composite result model, release record, installation history, or compensating rollback. On failure callers use the original execution error's result plus the Chart's phase snapshots. On cancellation callers use phase snapshots and the original cancellation exception.

## Errors and Warning

`ChartError` is the chart acquisition exception base. `ChartLoadError` adds `stage` (`source`, `index`, `download`, `archive`, or `metadata`), `category`, `source`, and optional `selector`. Categories distinguish invalid input, missing source, HTTP/timeout failures, absent chart/version, corrupt structure, unsafe members, and identity mismatch. Exceptions do not carry response objects, response bodies, or decoded template/value contents.

`ChartVersionWarning(UserWarning)` is a non-fatal unversioned ambiguity diagnostic. It identifies the chart and selected version while preserving successful first-entry loading. Lookup of all versions does not issue this warning.

Existing Apply usage/validation/execution errors and `CancelledError` remain their original types. Chart origin/relative-path context may be added as exception notes; `source`, result fields, causes, and identities retain their existing meaning.
