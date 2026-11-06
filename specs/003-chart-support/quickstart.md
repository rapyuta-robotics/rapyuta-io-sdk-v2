# Quickstart: Validate Chart Support

This guide validates the implemented Chart interfaces, tests, examples, and workflow capture suite. Normal checks need no rio installation or platform account.

## Prerequisites and Setup

- Python 3.13+ and uv with the project's runtime and development dependencies.
- Checked-in Apply parity fixtures and the new controlled chart/workflow fixtures.
- For explicit workflow oracle replay/refresh only: rio CLI checkout at the revision recorded in workflow provenance, with dependencies available to the SDK Python environment. Use the pinned chart checkout when copying/capturing real chart metadata.

From the repository root:

```bash
uv sync --group dev
export ANSIBLE_LOCAL_TEMP=/tmp/ansible-chart-parity
uv run pytest tests/chart -q
uv run pytest tests/apply -q
uv run pytest -q
uvx ruff==0.16.9 check .
uvx ruff==0.16.9 format --check .
```

Expected: source/transport/lifecycle safety tests pass, all six recorded chart cases pass through both facades, existing SDK/Apply regressions remain green, and lint/format checks pass. No credentials or live endpoints are used by those tests.

## Local Inspection and Preview

The implementation adds `examples/chart/sync_chart.py` and `examples/chart/async_chart.py` with the same argument contract. Their default action is offline inspection; actions `apply`/`delete` also require `--dry-run` or explicit `--config` for live work. `--values`/`--secrets` are repeatable plain sources; `--rio` is an optional plain YAML/JSON context mapping. `--config` reads an explicitly selected SDK configuration file, with client cleanup owned by the example. Source arguments `--directory`, `--archive`, and `--chart` are mutually exclusive.

```bash
uv run python examples/chart/sync_chart.py \
  --directory /path/to/chart --action inspect
uv run python examples/chart/sync_chart.py \
  --directory /path/to/chart --values /path/to/complete-values.yaml \
  --rio /path/to/rio.yaml --action apply --dry-run
uv run python examples/chart/async_chart.py \
  --archive /path/to/chart.tgz --values /path/to/complete-values.yaml \
  --action delete --dry-run
```

Expected: metadata and structured prepared/preview outcomes are available without a platform client. Valid templates requiring rio context or device interface data must receive that context; for interface lookup validate through the controlled fixture scenario rather than guessing a live device. Source files remain unchanged, and extracted artifacts are already gone when the prepared chart is returned.

Omitting values uses `values.yaml`; supplying even an empty mapping replaces defaults. A partial values file is not merged over defaults automatically. The public signatures and phase-result rules are in [chart-api.md](contracts/chart-api.md).

## Published and Branch Chart Preview

These commands make explicit repository requests to retrieve the chart. They still issue no platform resource requests:

```bash
uv run python examples/chart/sync_chart.py \
  --chart gateway:1.0.0 --values /path/to/complete-values.yaml \
  --rio /path/to/rio.yaml --action apply --dry-run
uv run python examples/chart/async_chart.py \
  --chart gateway:1.0.0 --branch 'bug/fix some' \
  --values /path/to/complete-values.yaml --rio /path/to/rio.yaml \
  --action apply --dry-run
```

An explicit `--repository` supplies an alternative index unless a non-empty branch selects the CLI branch index. Published chart availability is not an assumption of offline regression tests: controlled repository cases validate exact URLs and package selection. Repository listing/lookup returns metadata as data; [repository-format.md](contracts/repository-format.md) defines ordering and warning semantics.

## Recreation and Programmatic Failure Evidence

Use `--delete-existing` with `--action apply --dry-run` to validate both planned phases. Expected `phase_results` order is delete, apply, while the returned result is the final apply preview. In controlled execution tests, deletion failure/cancellation starts zero apply operations, and apply failure preserves its result plus successful deletion in the phase snapshots. Validate original exception types and no stale result after a rejected new preflight.

The examples demonstrate explicitly calling the existing secret-file decryption helper and passing its returned mapping into `ChartInputs`; Chart never implicitly decrypts `--secrets` sources. Live actions require a caller-selected configuration/client and remain optional application integration work. The example must not infer CLI login or a default configuration path.

## Explicit CLI Oracle Replay

Replay the workflow capture suite:

```bash
uv run python scripts/capture_apply_parity.py \
  --suite chart-workflows \
  --cli-root /home/ankit/Projects/Work/rapyuta-io-cli \
  --output tests/chart/fixtures/workflows --verify
```

Expected: controlled selection, URL, values, and callback-phase records match checked-in CLI output, including four branch encoding cases. Verification rejects provenance/environment drift and never overwrites expectations or accesses the platform. Explicit refresh uses `--write` instead of `--verify`; review its output and metadata before running SDK parity tests.

Existing Apply fixture replay remains unchanged:

```bash
uv run python scripts/capture_apply_parity.py \
  --suite charts \
  --cli-root /home/ankit/Projects/Work/rapyuta-io-cli \
  --charts-root /home/ankit/Projects/Work/rapyuta-charts \
  --output tests/apply/fixtures/parity --verify
```

The complete case matrix and ownership/cancellation acceptance evidence are in [parity-validation.md](contracts/parity-validation.md). Run capture only with recorded Python/Jinja/Ansible versions; ordinary pytest checks consume fixtures without loading the CLI.

## Recorded chart revisions

Workflow metadata is pinned to chart revision `94e456aea0dcdd7d4493aa57662cc0b8815df0ef` in `tests/chart/fixtures/metadata/provenance.json`. Existing Apply manifest fixtures retain their independently recorded revision in `tests/apply/fixtures/parity/provenance.json` (currently `f52c0c64866b30beddad619d84e4a912c5c7b744`). Replay the latter against an isolated checkout of that recorded revision rather than changing the user's active chart checkout or refreshing expectations. Source/input and environment drift is rejected before rendering.
