# Quickstart Validation: Reusable SDK Applier

This guide records how to validate the implemented reusable SDK applier. Exact contracts are in [contracts/applier-api.md](contracts/applier-api.md), [contracts/resource-interface.md](contracts/resource-interface.md), [contracts/resource-progress.md](contracts/resource-progress.md), and [contracts/sops-helper.md](contracts/sops-helper.md).

## Prerequisites and setup

Use Python 3.13 or 3.14, uv, and this repository's development dependencies. Ordinary automated validation needs neither rio nor platform credentials. The implementation adds Jinja and updates the dependency lockfile before these commands run.

From the repository root:

```bash
uv sync --locked --python 3.13 --all-extras --dev
uv run --python 3.13 pytest tests/apply/ tests/test_model_contracts.py
```

Expected: tests complete against controlled platform responses and subprocess fixtures, without installing rio, real SOPS credentials, or the older SDK. Repeat on Python 3.14 for the existing CI matrix.

## Offline preparation and preview

Create a disposable manifest directory with a small Role manifest:

```bash
mkdir -p /tmp/sdk-applier-preview
cat > /tmp/sdk-applier-preview/role.yaml <<'YAML'
apiVersion: api.rapyuta.io/v2
kind: Role
metadata:
  name: preview-role
spec:
  description: Preview validation
  rules: []
YAML
```

Run this usage example from the repository root:

```bash
uv run python - <<'PYTHON'
from pathlib import Path
from rapyuta_io_sdk_v2 import Applier, ManifestSource

applier = Applier(ManifestSource(files=(Path('/tmp/sdk-applier-preview/role.yaml'),)))
inspection = applier.inspect()
result = applier.apply(dry_run=True)
assert len(inspection.resource_identities) == 1
assert result.successful
assert result.outcomes[0].status == 'planned'
assert result.outcomes[0].planned_action == 'create_or_update'
PYTHON
```

Expected: one role is prepared and one truthful intended action is returned. No auth/configuration/client is needed, no platform request is issued, and no decryption command runs. The loading and graph tests cover ordered nested values, explicit rio/secrets namespaces, multiple YAML documents, empty documents, invalid extensions, missing kinds/versions, duplicates, cycles, and zero writes for rejected collections.

Distinguish validation timing explicitly: a valid Organization must prepare and inspect successfully; its non-retained delete and delete preview fail only at the requested operation's capability preflight. Preparing a valid response-only Secret/UserGroup instance does not require creation credentials for inspect/delete, while apply and apply preview perform creation-request conversion/validation. Constructor kind/model/identity/graph failures remain offline. Assert this staging rather than treating an unsupported alternative operation as invalid construction input.

```bash
uv run pytest tests/apply/test_loading.py tests/apply/test_graph.py
uv run python -m examples.applier.offline_preview
```

## Sync and async lifecycle parity

Use modeled fixtures and HTTPX controlled responses to exercise every operation in the 12-kind coverage matrix. Supplied Client and AsyncClient instances must be the exact objects used by resource methods; assert they remain open and their selected scope stays unchanged. Applier must never construct a replacement client or close the supplied transports, including on failures/cancellation. Missing or wrong-mode clients must fail before requests. Repeated operations must use fresh sorter and scope/lookup state. Reuse one prepared Applier with two clients/scopes sequentially and assert each call uses its passed client without carrying server routing names or resolved GUIDs between calls.

```bash
uv run pytest tests/apply/test_resource_interface.py tests/apply/test_lifecycle.py
uv run pytest tests/apply/test_client_ownership.py
```

Expected: equivalent created/updated/exists/deleted/absent/retained outcomes in both modes. Assert typed requests/responses and body aliases for credential-bearing SecretCreate, explicit UserGroup membership data, exact RoleBinding bulk grant/revoke, Project cache-disabled create followed by full update, and StaticRoute canonical names. Test create-denied/update-permitted fallback and denied creation on immutable apply kinds. Organization deletion fails preflight unless explicitly retained.

The `sync_apply.py` and `async_apply.py` examples construct their Client or AsyncClient explicitly from caller-selected SDK configuration, pass that instance to apply calls, and take explicit source paths. Run them only when intentionally exercising a configured platform collection. They demonstrate typed result/error handling and do not import rio. Offline tests remain the default validation route.

## Dependency ordering, concurrency, and readiness

```bash
uv run pytest tests/apply/test_progress.py tests/apply/test_scheduler.py tests/apply/test_cancellation.py tests/apply/test_readiness.py
```

Use event barriers rather than elapsed-time guesses: release two async resources only after both have started, ensure a third waits at workers=2, and check an unrelated task progresses. With workers=1, verify serial starts. Sync transport calls may block and do not promise overlapping HTTP.

Expected: prerequisite completion/readiness precedes dependent submission; delete reverses the edges. Two same-name package versions remain distinct, GUID aliases link known local resources, and external references receive no mutation. Check disk/network readiness, provisioning Project updates, explicitly waited Deployment prerequisites, missing responses, terminal states, and exhaustion. Count immediate polling rounds and between-round sleeps per target exactly; verify paginated lookup requests belong to the same round and reject repeated continuation tokens. Do not retry failed writes.

Force permanent failure and cancellation while workers are blocked, including simultaneous worker failures, an independently cancelled worker, and repeated caller cancellation. Verify no dependent starts after failure, no worker issues requests after return, successful mutation steps remain in results, interrupted writes report uncertainty, cancellation remains CancelledError, and last_result is settled. Test sync use from a running event loop before platform work and ensure no unawaited coroutine warnings.

For the progress contract, use controlled responses to distinguish Project create success/update failure, create/update success/readiness failure, cancelled write, and cancellation during later readiness. Prior completed_actions must survive a method raising; cancellation during readiness alone must not make prior confirmed writes uncertain. A rejected create followed by update contributes updated only. An unconfirmed response-validation failure reports write uncertainty. Direct callers supplying a fresh MutationJournal in ResourceContext must be able to inspect its immutable snapshot after the original cancellation. Assert distinct journals across resources/repeated calls, no duplicated completed steps, and exclusion from context model_dump/model_dump_json/repr and both JSON Schema modes; existing resource schemas remain unchanged.

## Optional SOPS helper

```bash
uv run pytest tests/apply/test_sops.py
```

The test executable supplies controlled JSON output and simulates nonzero exits, missing executable, invalid mappings, delayed exit, spawn cancellation, ignored termination, and repeated cancellation. It must accept filenames literally, and tests must compare source bytes before and after. Use a secret-looking sentinel in stdout/stderr/parser content and assert it does not appear in SDK exception messages, repr, traceback chains, logs, or automatically written files. Async tests prove unrelated work continues and the child has exited before cancellation returns.

For a real integration check, install SOPS independently, configure local decryption credentials, and prepare a non-production encrypted YAML/JSON mapping. Then use this explicit composition:

```python
from rapyuta_io_sdk_v2 import Applier, ManifestSource, decrypt_secret_file

values = decrypt_secret_file("/path/to/secret-values.enc.yaml")
applier = Applier(ManifestSource(files=("/path/to/manifest.yaml",), secrets=(values,)))
preview = applier.apply(dry_run=True)
```

Async callers await async_decrypt_secret_file before constructing AsyncApplier. Expected: returned values populate secrets, the encrypted source is unchanged, and preview makes no platform requests. Plain-secret callers never need SOPS. Once returned and supplied to ManifestSource, decrypted mappings have no special protection; Applier uses ordinary value handling and diagnostics. Confidential-diagnostic assertions apply to the SOPS helper itself. The `examples/applier/encrypted_secrets.py` script demonstrates both modes and prints only resource counts, not decrypted values.

## Final implementation checks

The completed implementation was validated on 2026-10-09 with:

```bash
uv run --no-sync --python 3.13 pytest tests/ --cov=rapyuta_io_sdk_v2 --cov-report=term:skip-covered
uv run --no-sync --python 3.14 pytest tests/ --cov=rapyuta_io_sdk_v2 --cov-report=term:skip-covered
uv run --no-sync --python 3.13 ruff check .
uv run --no-sync --python 3.13 ruff format --check .
uv run --no-sync --python 3.13 python -m examples.applier.offline_preview
uv build --out-dir /tmp/rapyuta-sdk-applier-dist
```

Results: 859 tests passed on Python 3.13.9 and 859 on Python 3.14.2; Ruff 0.16.9 and formatting checks passed; the offline example inspected one resource and produced sync and async plans; and both the wheel and source distribution built successfully. The distribution archives contain the new applier, scheduler, SOPS, and model modules. These are local checks; no publish/deploy step is part of this feature.

## Review correction validation (2026-10-12)

The four review defects are fixed: cross-scope dependency matching retains selected routing scope, direct RoleBinding grants reconcile metadata and context before requests, paired standard create/update hooks derive routing from reconciled scope, and inspection serialization preserves concrete manifest fields. Tasks T076–T080 track the corrections.

Added 62 regression cases covering both facades, client-derived apply/reverse-delete ordering, all affected paired standard write hooks, rejection before lookup/write, unchanged caller resources/context/journals, and inspection Python/JSON/alias/unset serialization.

Validation used the installed Python 3.13.9 and 3.14.2 environments:

```bash
.venv/bin/python -m pytest tests/ -q
COVERAGE_FILE=/tmp/rapyuta-sdk-review-314.coverage /tmp/rapyuta-sdk-applier-314/bin/python -m pytest tests/ --cov=rapyuta_io_sdk_v2 --cov-report=term:skip-covered -q
ruff check .
ruff format --check .
.venv/bin/python -m examples.applier.offline_preview
```

Results: 946 tests passed on each Python version, with 83% package coverage on Python 3.14. Ruff 0.16.9 lint/format checks and the offline example passed. Python 3.13 coverage instrumentation stalled in the existing SOPS async tests, including a run limited to `tests/apply/test_sops.py`; those tests pass without coverage. The stalled runs were stopped. The Python 3.13 coverage gate remains unverified.

Both distribution formats built successfully using `uv build --offline --no-build-isolation --python .venv/bin/python --out-dir /tmp/rapyuta-sdk-review-fixes-dist`, with cached Hatchling, Pathspec, and Trove Classifiers supplied through `PYTHONPATH` and `UV_CACHE_DIR=/tmp/uv-cache-sdk-applier-review`. Byte comparisons confirmed that both archives contain the updated graph, standard hooks, RoleBinding helpers, and inspection models. No extension hooks are configured.

## Additional review correction validation (2026-10-12)

Tasks T081–T086 address four further findings: supplied Package instances retain
normalized commands without rerunning model transformations; Organization
dependencies route through the target GUID; direct StaticRoute operations prefer
metadata scope over client defaults and reject context conflicts before reads;
and both facades guard previews with the active-operation lock, preserving
`last_result` when overlap is rejected and releasing the guard after failure.

Added 30 regression cases. Before correction, 22 focused cases failed; after
correction, all 73 tests in the four affected test modules pass. The cases cover
file/instance equivalence, nested unset fields and input isolation, Organization
graph matching and event-controlled execution order without an organization
default, paired StaticRoute create/update routing and conflict preflight, and
preview overlap and guard release in both facades.

```bash
.venv/bin/python -m pytest tests/apply/test_loading.py tests/apply/test_dependencies.py tests/apply/test_staticroute.py tests/apply/test_preview.py -q
timeout 40 .venv/bin/python -m pytest tests/ --ignore=tests/apply/test_sops.py -q
timeout 40 .venv/bin/python -m pytest tests/apply/test_sops.py -q -o faulthandler_timeout=15
COVERAGE_FILE=/tmp/rapyuta-sdk-review-second-314.coverage /tmp/rapyuta-sdk-applier-314/bin/python -m pytest tests/ --cov=rapyuta_io_sdk_v2 --cov-report=term:skip-covered -q
ruff check .
ruff format --check .
.venv/bin/python -m examples.applier.offline_preview
```

Results: all 976 tests passed on Python 3.14.2 with 84% package coverage. Python
3.13.9 passed all tests in separate runs (957 tests plus 19 SOPS tests); combined
runs stalled intermittently in existing async SOPS tests even without coverage
instrumentation and were stopped. An isolated SOPS error test also timed out.
The combined Python 3.13 run and its coverage gate remain unverified. Ruff
0.16.9 lint/format checks, whitespace validation, and the offline example passed.
Existing uncommitted changes were preserved. No extension hooks are configured.

## Scheduler typing validation (2026-10-12)

Tasks T087–T089 correct the scheduler's static lifecycle typing. Dispatch helpers
accept the existing typing-only `Resource` protocol, and prepared SDK models are
cast to that contract at dispatch and preflight boundaries. This removes six
unresolved lifecycle attributes and unnecessary return-value casts. Journal
snapshots retain `MutationAction` literals, resolving a seventh scheduler
diagnostic. These changes preserve runtime behavior and add no suppressions.

```bash
ty check rapyuta_io_sdk_v2/apply/_scheduler.py --python-version 3.13
ty check rapyuta_io_sdk_v2/apply/_scheduler.py --python-version 3.14
.venv/bin/python -m pytest tests/apply/test_scheduler.py tests/apply/test_cancellation.py tests/apply/test_lifecycle.py tests/apply/test_deletion.py tests/apply/test_progress.py tests/apply/test_client_ownership.py tests/apply/test_dependencies.py tests/apply/test_preview.py -q
ruff check .
ruff format --check .
```

Results: ty 0.0.84 reports no scheduler diagnostics for either Python target;
all 58 regression tests pass on Python 3.13.9; Ruff 0.16.9 lint/format and
whitespace checks pass. No extension hooks are configured.

## Resource ownership validation (2026-10-12)

Tasks T090–T094 move ordinary paired create/update/delete endpoint calls into
resource model methods, including simple Project and StaticRoute creation.
`apply/_resources/standard.py` now contains only shared scope reconciliation,
private-copy, routing-option, and mutation-recording utilities. Secret and
UserGroup models own creation-request conversion. UserGroup exact GUID lookup
lives in `apply/_resources/usergroup.py`; multi-call Project provisioning,
StaticRoute canonical resolution, and RoleBinding workflows remain helpers.

Disk, Network, Project, and Deployment own pure `readiness_state()` methods.
Generic sync/async polling consumes their typed interface and handles absent
observations centrally. Typed page protocols preserve resource types through
pagination; routing options declare only the keys they emit. The lifecycle
protocol's identity signature now uses the resource interface's ResourceScope.
Model fields, wire serialization, scope precedence, caller input isolation,
mutation journal behavior, readiness flags, and polling budgets are preserved.

Added 25 direct readiness cases, which failed before implementation. All 528
affected readiness/lifecycle/model-contract tests pass after the refactor.

```bash
timeout 60 .venv/bin/python -m pytest tests/ --ignore=tests/apply/test_sops.py -q
timeout 40 .venv/bin/python -m pytest tests/apply/test_sops.py -q -o faulthandler_timeout=15
COVERAGE_FILE=/tmp/rapyuta-sdk-resource-ownership-314.coverage /tmp/rapyuta-sdk-applier-314/bin/python -m pytest tests/ --cov=rapyuta_io_sdk_v2 --cov-report=term:skip-covered -q
ty check rapyuta_io_sdk_v2/apply/_scheduler.py rapyuta_io_sdk_v2/apply/_readiness.py rapyuta_io_sdk_v2/apply/_resources/standard.py rapyuta_io_sdk_v2/apply/_resources/usergroup.py --python-version 3.13
ty check rapyuta_io_sdk_v2/apply/_scheduler.py rapyuta_io_sdk_v2/apply/_readiness.py rapyuta_io_sdk_v2/apply/_resources/standard.py rapyuta_io_sdk_v2/apply/_resources/usergroup.py --python-version 3.14
ruff check .
ruff format --check .
.venv/bin/python -m examples.applier.offline_preview
```

Results: all 1,001 tests pass on Python 3.14.2 with 84% package coverage;
Python 3.13.9 passes 982 non-SOPS tests plus all 19 SOPS tests separately.
Targeted ty checks pass for both Python versions. All affected model files
except Network pass ty; Network's four pre-existing diagnostics are confined
to its unchanged legacy `list_dependencies` implementation. Both Ruff 0.16.9
checks, whitespace validation, and the offline example pass. Existing review
fixes are retained. No extension hooks are configured.

## Acceptance mapping

| Spec outcomes | Evidence |
| --- | --- |
| SC-001, SC-002 | Resource conformance plus 12-kind modeled lifecycle parity |
| SC-003 | Dependency/GUID/package-version and reverse-deletion tests |
| SC-004 | Offline preview, rejected preflight, retention, and request-count assertions |
| SC-005 | Async event barriers, worker bounds, and unrelated-task progress |
| SC-006 | Retained mutation journals, failure/cancellation snapshots, cleanup, and zero post-return work |
| SC-007 | Standalone examples and structured result/error use |
| SC-008 | SOPS fixture parity, source immutability, no platform access, confidential helper diagnostics |
