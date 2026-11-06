# Validation Guide: Configtree Import and Fast Merge

This guide validates the implemented feature. Use [the public contracts](contracts/sdk-interface.md) and [context lifecycle](contracts/revision-lifecycle.md) for exact semantics.

## Prerequisites and setup

- Python 3.13+ and uv, as documented in `CONTRIBUTING.md`.
- Dependencies installed from the existing lockfile; no new dependency is planned.
- For optional live validation, an authenticated configuration file, configured organization/project GUIDs, and two existing test trees with usable committed heads. Use trees intended for validation because the publication examples create revisions and advance the target head.
- The source test tree must contain compatible key-value entries: use disjoint paths or data/metadata identical to shared destination paths.

From the repository root:

```bash
uv sync --locked --dev
uv run python -c "from rapyuta_io_sdk_v2.configtree import Revision, AsyncRevision, import_configtree, import_configtree_async, merge_configtree, merge_configtree_async, parse_refspec"
```

Expected: imports succeed without CLI configuration, state files, prompts, or network requests.

## Automated acceptance checks

Run focused transformation, workflow, and transport checks first:

```bash
uv run pytest tests/test_configtree_helpers.py tests/sync_tests/test_configtree_operations.py tests/async_tests/test_configtree_operations_async.py tests/sync_tests/test_configtree.py tests/async_tests/test_configtree_async.py tests/test_model_contracts.py tests/sync_tests/test_pydantic_source.py
```

Expected: exact metadata recognition/traversal; three-file mixed-format import, empty-root rejection, and duplicate validation; equivalent sync/async results; six refspec forms; cross-scope routing; late-page milestone ambiguity and exact returned-label checks; compatible unions; zero mutation on conflict or inconsistent source content length; live dictionary edits and invalid mutated-model detection; one/zero batch call counts; sequenced publication; original exceptions and cancellation with recovery annotations; canonical batch URL and optional-query parity.

After focused checks pass, run the SDK regression and quality gates:

```bash
uv run pytest tests/ --cov
uvx ruff==0.16.9 check .
uvx ruff==0.16.9 format --check .
```

Expected: all tests pass, including unchanged settings-source behavior; no lint/format violations. Repeat using Python 3.14 according to `.github/workflows/quality-checks.yml`. Existing CI covers both supported verification interpreters.

## Optional live validation fixtures

Create named files in a scratch directory:

```bash
mkdir -p /tmp/rio-sdk-configtree-validation
cat > /tmp/rio-sdk-configtree-validation/robot.json <<'JSON'
{
  "navigation": {
    "speed": {"value": 2, "metadata": {"unit": "m/s"}},
    "enabled": {"value": false, "metadata": {}}
  },
  "label": "ロボット",
  "waypoints": [1, 2]
}
JSON
cat > /tmp/rio-sdk-configtree-validation/site.yaml <<'YAML'
region: east
retries: 0
optional: null
YAML
```

Set `RIO_CONFIG` to the path of an existing SDK configuration file, `RIO_TARGET_TREE` to the test destination name, and `RIO_SOURCE_REF` to a compatible source such as `org/test-defaults/release`. Never print authentication fields. Names must refer to trees you are authorized to mutate/read.

## Synchronous Import and Merge

```python
import os
from pathlib import Path

from rapyuta_io_sdk_v2 import Client, Configuration
from rapyuta_io_sdk_v2.configtree import (
    ImportOptions,
    import_configtree,
    merge_configtree,
)

client = Client(Configuration.from_file(os.environ["RIO_CONFIG"]))
files = [
    Path("/tmp/rio-sdk-configtree-validation/robot.json"),
    Path("/tmp/rio-sdk-configtree-validation/site.yaml"),
]
try:
    imported = import_configtree(
        client,
        os.environ["RIO_TARGET_TREE"],
        files,
        options=ImportOptions(commit=True, update_head=True),
    )
    merged = merge_configtree(
        client, os.environ["RIO_TARGET_TREE"], os.environ["RIO_SOURCE_REF"]
    )
    print(imported, merged)
finally:
    client.c.close()
```

Expected Import content includes `robot/navigation/speed` with `unit=m/s`, `robot/navigation/enabled` with empty metadata, the unchanged Unicode label, one list-valued `robot/waypoints`, `site/region`, `site/retries`, and `site/optional`. No `.../value` or metadata field paths are emitted for genuine wrappers. Import creates one committed revision and selects it as head. Merge then creates one committed compatible-union revision and selects that new head. Re-read the returned revisions using `get_configtree(..., revision=<ID>, include_data=True, content_types=["kv"])`; compare typed content and metadata with the contract.

Repeat Import with all four commit/head combinations. Default options leave the old head selected. Commit-only creates a committed revision without changing the head. Head-only attempts selection after storage; if the platform rejects an uncommitted head, verify the failure's revision ID/stage and stop.

## Asynchronous validation

The following snippet runs within an existing async application or interactive async session:

```python
import os
from pathlib import Path

from rapyuta_io_sdk_v2 import AsyncClient, Configuration
from rapyuta_io_sdk_v2.configtree import (
    ImportOptions,
    import_configtree_async,
    merge_configtree_async,
)

client = AsyncClient(Configuration.from_file(os.environ["RIO_CONFIG"]))
files = [
    Path("/tmp/rio-sdk-configtree-validation/robot.json"),
    Path("/tmp/rio-sdk-configtree-validation/site.yaml"),
]
try:
    imported = await import_configtree_async(
        client,
        os.environ["RIO_TARGET_TREE"],
        files,
        options=ImportOptions(commit=True, update_head=True),
    )
    merged = await merge_configtree_async(
        client, os.environ["RIO_TARGET_TREE"], os.environ["RIO_SOURCE_REF"]
    )
    print(imported, merged)
finally:
    await client.c.aclose()
    client.sync_client.close()
```

Expected: identical content, metadata, scope, and publication outcomes to the synchronous scenario, with independently generated revision IDs. The test suite must also cancel at awaited creation/storage/commit/head boundaries and prove no later stage starts. Cancellation retains `CancelledError`; known revision IDs remain available via exception annotations or the held context.

## Editable pending dictionary

With a configured synchronous `client` and test `tree_name`:

```python
from rapyuta_io_sdk_v2.configtree import Revision, RevisionOptions

with Revision(client, tree_name, options=RevisionOptions(commit=True)) as revision:
    pending = revision.keys
    revision.store("manual/speed", 2, metadata={"unit": "m/s"})
    revision.store("manual/drop", 1)
    pending["manual/speed"].metadata = {"unit": "meters-per-second"}
    del pending["manual/drop"]
    assert pending is revision.keys
print(revision.revision_id)
```

Expected: a fresh revision, one batch containing only the final pending `manual/speed` entry, then commit. The head is not selected by the context. Parent-inherited keys remain inherited even when absent from the pending dictionary. Repeat with `async with AsyncRevision(...)`; staging calls and dictionary edits remain synchronous local operations.

MockTransport tests establish write counts; a live server observation alone cannot prove no hidden per-key requests. A mutated entry containing invalid metadata types or a stale checksum must fail final validation before batch/commit. Clearing the pending dictionary makes zero batch calls; any requested commit still follows the normal lifecycle.

## Failure scenarios and completion criteria

Use the automated transport fixtures to inject file errors, conflicts, late-page duplicate milestones, mismatched returned milestone labels, inconsistent source content lengths, unsuccessful batch envelopes, storage/commit/head errors, and cancellation. An inconsistent source length must identify its key and create no destination revision. Check the existing head for failures before dispatch; after a dispatched mutation, remote completion may be uncertain. Inspect `getattr(error, "configtree_revision_id", None)`, `configtree_stage`, and exception notes for recovery rather than relying on automatic rollback.

The feature is ready when all automated acceptance/regression checks and both Ruff gates pass, the documented public examples run in their intended execution mode, and observations match SC-001 through SC-010. Live platform validation remains optional and requires caller-owned test trees and credentials.

## Implementation validation record

The public import smoke check and documented focused acceptance command passed.
The current implementation was checked with `uv run --locked --offline --python
3.13 pytest -q tests/ --cov` and the same command with `--python 3.14`:

| Interpreter | Full test suite | Overall coverage |
| --- | --- | --- |
| Python 3.13.9 | 863 passed | 94% |
| Python 3.14.2 | 863 passed | 94% |

Ruff 0.16.9 passed `ruff check .` and `ruff format --check .`, with 107 files
formatted. These checks use mocked transport and local files; no live platform
calls were made.
