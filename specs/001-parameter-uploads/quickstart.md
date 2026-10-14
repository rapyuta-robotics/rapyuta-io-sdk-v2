# Quickstart Validation: Parameter Uploads

The typed v1 operations and both directory helpers are implemented. See the
[SDK contract](contracts/sdk.md), [model definitions](data-model.md), and
[storage contract](contracts/storage.md) for their public interfaces and wire
behavior. Python 3.13+ is required; validation used Python 3.13.9.

## Install the verification environment

```bash
uv sync --group dev --group reference
```

The test-only `reference` group installs `rapyuta-io` from SDK source revision
`739a6fe44600ff0964fa56b04878ddb21e76b5be`. The lock file preserves that revision;
it adds no runtime dependency to SDK v2. The inspected CLI download command
uses this SDK's public `Client.download_configurations`. Its incompatible declared
SDK dependency range is the reason the CLI is not installed alongside this pin.

## Submit directories

Arrange immediate child directories as tree roots:

```text
source/
├── settings/
│   ├── config.yaml
│   ├── image.bin
│   └── empty-folder/
└── secrets/
    └── config.json
```

Provide credentials and a project before running either example:

```bash
export RAPYUTA_AUTH_TOKEN='<token>'
export RAPYUTA_PROJECT_GUID='<project-guid>'
export RAPYUTA_ENVIRONMENT=ga
uv run python examples/parameters/upload.py /path/to/source --tree settings
uv run python examples/parameters/upload_async.py /path/to/source --tree settings --inspect
```

Production/staging core endpoints resolve automatically. For local use, provide
`RAPYUTA_CORE_API_HOST` to the examples, `Configuration.core_api_host`, or
`LOCAL_COREAPI_HOST`. The value must be an HTTP(S) origin without a path, query,
fragment or credentials. Local v2 operations remain usable without a core host.

Both examples accept repeated `--tree` filters, `--recreate`, `--legacy`,
`--environment`, and `--core-api-host`. Defaults upload all immediate directories
in folder mode and fail on existing roots. Recreation deletes only selected
trees after source preflight. Legacy mode alternates value/attribute directories,
requires at most one attribute child under a value directory, rejects repeated
attribute names or directory extensions, and reports attribute-level files as
skipped. Use a source layout satisfying those legacy constraints.

For programmatic use:

```python
from rapyuta_io_sdk_v2 import Client, Configuration, ParameterUploadOptions
from rapyuta_io_sdk_v2.exceptions import ParameterUploadError
from rapyuta_io_sdk_v2.helpers import upload_parameters

config = Configuration.from_file()
client = Client(config)
try:
    result = upload_parameters(
        client,
        "/path/to/source",
        options=ParameterUploadOptions(tree_names=("settings",)),
    )
    print(result.model_dump_json(indent=2))
except ParameterUploadError as error:
    print(error.failure.path, error.failure.stage)
    print(error.partial_result.model_dump_json(indent=2))
finally:
    client.c.close()
```

Async usage is in [upload_async.py](../../examples/parameters/upload_async.py).
It inspects `ParameterUploadCancelled.failure` and `.partial_result` before
re-raising cancellation and closing the caller-owned resources.

Small YAML mappings and valid JSON preserve their original UTF-8 text, including
CRLF line endings. Validation precedes the reference stored-size estimate
(`len(json.dumps(payload)) + 200`); above 128 KiB, content uses blobs. Raw files
above 131072 bytes and other extensions bypass structured parsing. Each eligible
file is classified once. The supported maximum blob size is 209715200000 bytes;
larger files fail preflight. Transfers use at most one 4 MiB block payload,
Base64 MD5 storage headers, and a second source/hash check before finalization.
Async prehashing has cancellation checkpoints between bounded reads.

Results include confirmed roots/directories, files, tree completions, deletions
and inspected skips. Ordinary errors and cancellation expose immutable snapshots
of known progress; unacknowledged operations are not marked complete. Remote
changes can remain after failure. Caller-owned platform/storage clients stay
open; helpers close the storage clients they create.

## Automated verification

```bash
uv run --group reference pytest tests/test_parameter_models.py tests/test_parameter_storage.py tests/sync_tests/test_parameter.py tests/async_tests/test_parameter_async.py tests/helpers/test_parameter_upload.py tests/helpers/test_parameter_upload_async.py
uv run --group reference pytest tests/test_model_contracts.py tests/sync_tests/test_config.py tests/sync_tests/test_configtree.py tests/async_tests/test_configtree_async.py tests/sync_tests/test_pydantic_source.py
uv run --group reference pytest
uvx ruff==0.16.9 check .
uvx ruff==0.16.9 format --check .
```

Tests use HTTPX MockTransport and mocked requests; no platform/storage request
leaves the isolated services. In the implementation environment, downloads and
threaded tests used approved execution outside the filesystem sandbox: the
sandbox blocks the local IPC asyncio needs to receive disk-worker completions.
Tool caches were directed to `/tmp/parameter-uv-cache` and
`/tmp/parameter-uv-tools`, rather than changing SDK behavior.

## Mandatory actual-consumer gate

```bash
uv run --group reference pytest tests/reference/test_parameter_compatibility.py -q -rs
```

This runs the actual pinned SDK v1 public downloader against tree/blob state
produced by both helpers, blocking unhandled network requests. It compares
eligible paths, empty folders, original inline bytes and binary content for
folder and legacy modes. Fixtures exercise two trees, at least 100 mixed files,
five levels, filtering/recreation, duplicate references, zero-byte and multi-block
files, exact/one-byte-over stored-size boundaries, raw-size boundaries and Unicode
escaping. Source metadata tests separately check the maximum supported blob size.

`tests/reference/conftest.py` rejects wrong dependency provenance and fails the
pytest command when required cases are skipped or no reference case executes.
Deliberate skip and deselection probes both returned exit status 1 as required.
Those negative probes are separate from the six successful compatibility cases.

## Recorded results (2026-10-13)

| Check | Result |
| --- | --- |
| Dependency setup | Pinned SDK v1 `3.0.0`, exact git revision above installed |
| Existing test baseline | 740 passed |
| Focused contract/configuration/ConfigTree/source regressions | 488 passed |
| Full suite | 1012 passed, 0 failed, 0 skipped (8.75 seconds) |
| Required SDK v1 consumer gate | 6 passed, 0 failed, 0 skipped (final implementation) |
| Feature coverage inspection before final path audit | 96% statements; models/orchestration/progress 100% |
| Pinned Ruff lint and format | Both passed with Ruff 0.16.9 |
| Executable example smoke workflows | 8 passed, 0 live requests, clients closed |
| Example `--help` imports and argument parsers | Both passed |
| Zero-execution and skipped-case gate probes | Both failed with exit 1, as intended |

The eight example smoke workflows exercised sync/async, exact selection,
inspection, preservation/recreation, and folder/legacy mode against isolated
transports. Reference provenance comes from installed `direct_url.json` and
matches the pinned revision. No checklist markers were changed during
implementation. No extension hooks are configured.

## Convergence implementation results (2026-10-14)

Completed T050-T056 with 96 additional regression cases. All nine Parameter
methods in both clients disable redirects, serialize revalidated query values,
and reject decoded top-level error keys. Preflight OS errors identify the
failing child; non-UTF-8 error bodies preserve SDK status mappings. Public
failure/cancellation text and verification notes redact signed queries for
uppercase and mixed-case HTTP(S) schemes while retaining original causes.

Storage regressions inject same-size second-pass corruption without changing
content/identity metadata, reject the final block list after accepted blocks,
and fail/cancel both owned and injected storage clients. They verify no binary
confirmation or later work, acknowledged partial progress, owned-client cleanup,
and caller-client ownership. Access time is excluded from metadata comparisons
because reading a file may update it.

| Check | Result |
| --- | --- |
| Full suite with reference dependencies | 1108 passed, 0 failed, 0 skipped (17.62 seconds) |
| Separate actual SDK v1 downloader gate | 6 passed, 0 failed, 0 skipped (1.08 seconds) |
| Additional convergence regressions | 96 passed within the full suite |
| Pinned Ruff lint and format | Both passed with Ruff 0.16.9 |
| Executable example smoke workflows | 8 passed, 0 live requests, all clients closed |

The earlier baseline and coverage figures above are historical results, not a
new coverage measurement. Checklist markers remain unchanged. No extension
hooks are configured. Live deployment validation remains supplemental and was
not performed.

## Remaining verification results (2026-10-14)

Completed T057-T058 with 68 additional regression cases: 36 connection/read
failures across all nine operations in both client modes, 12 version conflicts
on child writes/deletions and binary preparation, and 20 preparation/storage/
helper metadata cases. The failure cases retain the original transport exception
or service exception/status, preserve the supplied version, and issue exactly
one request with no refresh. Metadata cases verify typed-header precedence,
encoding omission, plain files and real gzip streams, and MIME/encoding on both
Put Blob and final Put Block List. Existing byte, checksum, SAS-query and
credential-isolation checks remain in place. No application change was required.

| Check | Command | Result |
| --- | --- | --- |
| Parameter operation suites | `.venv/bin/python -m pytest tests/sync_tests/test_parameter.py tests/async_tests/test_parameter_async.py -q` | 150 passed before T058's four preparation cases |
| New metadata cases | `.venv/bin/python -m pytest tests/sync_tests/test_parameter.py tests/async_tests/test_parameter_async.py tests/test_parameter_storage.py tests/helpers/test_parameter_upload.py tests/helpers/test_parameter_upload_async.py -k 'preparation_metadata_overrides or storage_media_properties or helper_preserves_blob_media_metadata' -q` | 20 passed |
| Full suite | `uv run --group reference pytest -q` | 1176 passed, 0 failed, 0 skipped (22.34 seconds) |
| Actual pinned SDK v1 downloader | `uv run --group reference pytest tests/reference -q -rs` | 6 passed, 0 failed, 0 skipped (2.02 seconds) |
| Pinned lint | `uvx ruff==0.16.9 check .` | Passed |
| Pinned formatting | `uvx ruff==0.16.9 format --check .` | Passed; 112 files formatted |

Final commands used cached tooling with `UV_OFFLINE=1` and the `/tmp` cache
locations described above. Async worker tests used approved execution with
local IPC; service traffic remained mocked. All 58 tasks are complete. The
checklist remains 16 checked / 0 unchecked, and no extension hooks are configured.
Earlier verification and coverage measurements above remain historical evidence.
Live-service validation was not performed.

## Supplemental live checks

Unavailable: no disposable live project or scoped live-test credentials were
provided. No live upload, deletion, CLI download or deployed-service validation
was attempted. The mandatory offline consumer gate ran independently of this
limitation; its passing result establishes compatibility for the exercised
fixtures, rather than live deployment behavior.
