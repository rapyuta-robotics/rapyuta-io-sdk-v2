# Device Management Validation Guide

This guide describes the implemented interfaces and executable validation files. Actual isolated verification results are recorded below. See [contracts/sdk.md](contracts/sdk.md) for exact method/response shapes and [data-model.md](data-model.md) for field validation.

## Prerequisites and setup

Use Python 3.13+ and the repository's uv workflow. From the repository root:

```bash
uv sync --group dev --group reference
```

The reference group already pins SDK v1; do not replace it with an unpinned release. Mandatory tests use source-derived fake identities/tokens, mocked HTTP transports, and controlled clocks. They must not use environment credentials or a live service. Missing reference tooling or skipped required cases is a failure, not a successful compatibility run.

## Required isolated checks after implementation

```bash
uv run pytest tests/test_device_models.py tests/test_device_command_models.py tests/sync_tests/test_device.py tests/async_tests/test_device_async.py
uv run pytest tests/helpers/test_device_command.py tests/helpers/test_device_command_async.py
uv run pytest tests/reference/test_device_compatibility.py
uv run pytest tests/test_model_contracts.py tests/test_device_api.py tests/test_device_errors.py tests/test_device_examples.py
uv run pytest
uvx ruff==0.16.9 check .
uvx ruff==0.16.9 format --check .
```

Expected outcomes:

- All 20 operation contracts pass in both modes, with matching public signatures/defaults/models, exactly one request per client call, correct context overrides, and no public topic/agent-upgrade/general-daemon mutation methods.
- Lifecycle fidelity checks compare transmitted request values and returned device identifiers exactly. They preserve historically ignored registration inputs and documented no-op updates without asserting that the service persists those values or that an acknowledgment establishes readiness.
- Source-derived fixtures cover token registration, scalar/record routing, label maps and empty acknowledgments, config restrictions, selection grammar, Parameter outcomes, migration refusals, and actual wrapped VPN Daemon response including sshcert_config.
- A deferred three-device command receives staggered output, retains empty output, submits once, and preserves earlier responses. Malformed/incorrect targets/jobs and terminal HTTP failures do not become success or pending.
- Only the exact HTTP400 lookup envelope 'Job not found or incomplete' is pending. Unknown jobs use that same service marker and eventually time out; changed messages and submission errors are terminal.
- Budget tests cover elapsed submission/retrieval time, bounded sleeps, individual timeout caps, zero work started after expiry, and a late sync result producing timeout even if all responses are present. Async cancellation/deadline tests preserve typed context and progress of a 50 ms heartbeat with gaps no greater than 250 ms in controlled conditions.
- Caller inputs, supplied transports, headers, and default timeouts remain unchanged; clients remain open after helpers. No automatic resubmission or remote cancellation occurs.
- Every workflow failure or cancellation exposes failure.stage, failure.message, failure.jid, failure.requested_devices, and failure.missing_devices. Its identity fields exactly match the associated partial_result snapshot; completed outputs remain in partial_result.responses and unavailable job identity is None.
- Actual pinned SDK public request serialization is replayed in isolation for compatible operations; canonical slash corrections and corrected helper semantics are checked against server evidence. No required case is skipped and no live request is sent.
- Shared HTTP error handling, Daemon reads, file uploads, Parameter operations/helpers, model exports, and the existing suite still pass.

The foundational T009 verification gate is complete only when its required tests pass. If tooling blocks them, record the blocker and keep that task unchecked. Evidence gathering and draft documentation/test cases may continue, but story implementation and dependent completion wait for the foundational checks; a recorded blocker is never passing verification evidence.

## Supplemental live validation prerequisites

Use a disposable project and explicit devices the operator is permitted to manage. The example programs read these environment variables explicitly through their local configuration helper:

```text
RAPYUTA_AUTH_TOKEN       existing platform authentication token
RAPYUTA_PROJECT_GUID     source/disposable project
RAPYUTA_ORGANIZATION_GUID optional organization context
RAPYUTA_ENVIRONMENT      ga or the configured test environment
RAPYUTA_CORE_API_HOST    optional explicit service origin
RAPYUTA_DEVICE_GUID      one online device
RAPYUTA_DEVICE_GUIDS     comma-separated explicit online device identifiers
```

Do not use names, regular expressions, or numeric selection IDs as device GUIDs. Supply the existing organization context where registration requires it. No live result substitutes for isolated compatibility checks.

## Discovery, registration, and VPN

Run the management examples:

```bash
uv run python examples/devices/manage.py --help
uv run python examples/devices/manage_async.py --help
```

They provide explicit actions for listing/inspection, registration and onboarding authorization, labels/config, VPN enable/disable and route advertisement, Parameter application, and migration. A registration example submits a unique device name and at least one enabled runtime. Its success displays the returned device ID without printing a real token; a separate onboarding example exposes the script command only when explicitly requested. It does not run the installer.

For individual calls in a Python session with an existing configured `client`:

```python
from rapyuta_io_sdk_v2.models import DeviceCreate, DeviceVPNUpdate

listed = client.list_devices()
print([device.uuid for device in listed.response.data])

created = client.create_device(
    DeviceCreate(
        name="robot-alpha",
        config_variables={"runtime_docker": True},
        labels={"fleet": "alpha"},
    )
)
device_guid = created.response.device_id
print(device_guid)  # The response data is an onboarding token, not a Device.

vpn = client.set_device_vpn(device_guid, DeviceVPNUpdate(vpn=True))
print(vpn.response.data.kind)  # DeviceDaemon; acceptance is not readiness.
client.set_device_vpn(device_guid, DeviceVPNUpdate(vpn=False))
```

Use an onboarded eligible device for VPN actions; a freshly registered identity alone is not proof that hardware/agents are ready. VPN with advertised routes uses `DeviceVPNUpdate(vpn=True, config={"vpn":{"advertise_routes":True}})` and project-configured routes; disabling with advertisement true fails locally. The default does not advertise routes. Async validation awaits the same methods and uses identical models.

## Direct command operations

With an existing configured client and an explicit online `device_guid`:

```python
from rapyuta_io_sdk_v2.models import (
    DeviceCommand,
    DeviceCommandJob,
    DeviceCommandPendingResponse,
    DeviceCommandResultQuery,
)

submitted = client.execute_device_command(
    DeviceCommand(device_ids=(device_guid,), cmd="printf 'ready\\n'", run_async=True)
)
job = submitted.response.data.root
assert isinstance(job, DeviceCommandJob)
lookup = client.get_device_command_result(
    job.jid, query=DeviceCommandResultQuery(device_ids=(device_guid,))
)
if isinstance(lookup, DeviceCommandPendingResponse):
    print("Still waiting")
else:
    print(lookup.response.data.root)
```

A direct lookup makes one request and never sleeps or polls internally. Immediate calls return device/output maps through the named variant instead of a job. Detached background launch returns its acknowledgment; use the response-waiting helper only for commands whose results can be collected.

## Synchronous helper

With the same configured client and explicit device identifiers:

```python
from rapyuta_io_sdk_v2.exceptions import DeviceCommandError
from rapyuta_io_sdk_v2.helpers import execute_device_command
from rapyuta_io_sdk_v2.models import DeviceCommand, DeviceCommandWaitOptions

try:
    outcome = execute_device_command(
        client,
        DeviceCommand(
            device_ids=("device-a", "device-b", "device-c"),
            cmd="printf 'ready\\n'",
            run_async=True,
        ),
        options=DeviceCommandWaitOptions(wait_timeout=30, poll_interval=1),
    )
    for response in outcome.responses:
        print(response.device_guid, repr(response.output))
except DeviceCommandError as error:
    print(error.failure.stage, error.partial_result.jid)
    print(error.partial_result.missing_devices)
    raise
```

Replace fake identifiers with permitted explicit targets for live use. Expected isolated fixture outputs include one empty string that still counts as received. `DeviceCommandTimeout` is both a workflow error and TimeoutError and carries the same partial snapshot. A valid response received after the deadline enriches known context but never becomes whole-operation success. A synchronous in-flight request can finish later because network-operation timeouts are not a strict wall-clock deadline.

`examples/devices/command.py` supports one or multiple targets, immediate/deferred mode, timeout/options, and error inspection. With real configured GUIDs:

```bash
uv run python examples/devices/command.py --device "$RAPYUTA_DEVICE_GUID" --command "printf 'ready\\n'"
uv run python examples/devices/command.py --device "$RAPYUTA_DEVICE_GUID" --command "printf 'ready\\n'" --mode deferred --wait-timeout 30 --poll-interval 1
```

Repeat `--device` for multiple explicit targets. Empty output can be checked with `--command "true"` and must still yield a received response. A deliberately delayed deferred command, e.g. `sleep 5; printf 'ready\\n'` with a one-second wait budget, exercises partial timeout; the remote command may continue afterward. Do not automatically resubmit it.

## Asynchronous helper and cancellation

`execute_device_command_async` uses the same command/options/result models. It awaits network I/O and polling sleeps. Run the planned examples:

```bash
uv run python examples/devices/command_async.py --device "$RAPYUTA_DEVICE_GUID" --command "printf 'ready\\n'" --mode deferred
uv run python examples/devices/command_async.py --device "$RAPYUTA_DEVICE_GUID" --command "sleep 5; printf 'ready\\n'" --mode deferred --cancel-after 1
```

The asynchronous example supports the same flags as the synchronous one plus `--cancel-after`. Its cancellation handler inspects `DeviceCommandCancelled.failure` and `.partial_result`, then re-raises cancellation. A known job can be retrieved explicitly later. Cancellation during submission may leave acceptance unknown and must not trigger another submission.

Use the caller's existing async resource-release convention: close `client.c` with `aclose()` and the existing auxiliary `client.sync_client` when the caller is finished. Helpers close neither. No new synchronous authentication or shutdown behavior is introduced by this feature.

## Implementation verification

Python 3.13.9 and the existing development/reference dependency groups were installed with `uv sync --group dev --group reference`. The reference distribution identifies commit `739a6fe44600ff0964fa56b04878ddb21e76b5be`. Baseline Ruff 0.16.9 lint and formatting checks passed.

Foundation gate: `.venv/bin/python -m pytest tests/test_device_api.py tests/sync_tests/test_utils.py` passed (87 tests). This verifies core-host routing, preserved v2 routing, scalar validation, strict envelopes, explicit-value serialization, and nested HTTP error messages before story implementation.

Lifecycle checkpoint: model and both client contract suites passed (26 tests), including all seven operations, literal registration/configuration values, update ID injection, token redaction, selection constraints and returned identity envelopes. Serialization does not promise persistence of server-ignored values.

Direct-command checkpoint: foundation/command-model/both-client checks passed (60 tests). This covers exact pending recognition, strict output strings, all operational defaults, both flags' background precedence and bounded network phases without mutation of defaults.

Helper checkpoint: sync/async helper and command-model suites passed (28 tests). Executed cases cover one submission, ordered staggered outputs, empty output, incomplete/foreign/conflicting results, unknown acceptance on interrupted submission, terminal shorter transport timeout, pending budget exhaustion, synchronous late output retained only in timeout context, cancellation during submission/retrieval/sleep, and a 50 ms heartbeat with gaps at most 250 ms. Async expiry remained within the one-second tolerance.

Management checkpoint: models and both complete operation suites passed (64 tests), including all 20 paired operations. VPN parses the actual DeviceDaemon, SSH certificate and pull-secret fields. Configuration read emptiness, write constraints, Parameter omissions and canonical routes are preserved.

### Final acceptance after convergence (2026-10-14)

Tooling: Python 3.13.9, HTTPX 0.28.1, Pydantic 2.13.4 and Ruff 0.16.9. No runtime dependencies or package identity were changed.

| Executed gate | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_device_api.py tests/test_device_models.py tests/test_device_command_models.py tests/sync_tests/test_device.py tests/async_tests/test_device_async.py tests/helpers/test_device_command.py tests/helpers/test_device_command_async.py tests/reference/test_device_compatibility.py tests/test_model_contracts.py tests/test_device_errors.py tests/test_device_examples.py -q -p no:cacheprovider` | 1,002 passed in 10.62 seconds; no skips |
| `uv run pytest -q -p no:cacheprovider` | 1,776 passed in 19.57 seconds; no skips |
| `uvx --offline ruff==0.16.9 check . --no-cache` | All checks passed |
| `uvx --offline ruff==0.16.9 format --check . --no-cache` | 143 files already formatted |
| `git diff --check` | Passed |

The Device reference gate includes 39 executed cases: 18 actual pinned v1 public-operation serialization replays, 20 canonical v2/controller goldens and a live-network rejection check. v1's redundant lookup jid parameter, missing canonical trailing slashes, mutable metadata objects and implicit selection orchestration are intentionally corrected by the documented v2 contracts. Migration and explicit selection use source-backed controller goldens where v1 has no equivalent standalone manager operation.

The examples and all Python quickstart snippets run against isolated fixtures. They cover every management action, direct commands, single/multiple targets, immediate/deferred execution, empty output, partial timeout and re-raised asynchronous cancellation. The examples explicitly read the documented environment variables into Configuration; they do not depend on the SDK's unimplemented Configuration.from_env.

Two sandboxed full-suite attempts stalled in the existing async Parameter mixed-source upload test. Diagnostic stacks showed an event-loop selector wait and an idle worker thread. The same isolated test passed outside the sandbox (0.16 seconds), and the complete suite then passed outside the sandbox. The final full regression gate above used that environment; the feature suites ran successfully in the sandbox.

### Requirement reconciliation

| Requirements | Executed evidence |
| --- | --- |
| FR-001–003, SC-001–002 | Twenty paired operation goldens, exact transmitted values/envelopes, per-call core host/context overrides, returned identities, typed raw-dict rejection and signature/default/annotation/export parity; list/get/update health reports populate daemon_status through the daemons_status wire alias and reject malformed reports |
| FR-004–005 | Strict command models, operational default emission, exact text, background precedence, deferred jobs, repeated device_id queries and exact pending recognition |
| FR-006–007, FR-012, SC-003 | One submission, three staggered batches, empty output, original target order, identical repeats, contract failures retaining all valid outputs independently of foreign/conflicting key ordering, and exact accepted-minion validation |
| FR-008, SC-005 | Controlled monotonic budget consumption, bounded polling pauses, no new work after expiry, all four actual transport timeout caps, late synchronous response snapshots, cancellable async expiry and the 50 ms heartbeat |
| FR-009–011, SC-004 | Preflight revalidation/background refusal; submission/retrieval/contract/incomplete-result stages; preserved causes and job identities, including real-client execution-mode mismatches and requested jid output kept distinct from job identity; frozen matching failure/outcome identity; unknown acceptance and cancellation during submission/retrieval/sleep with partial output |
| FR-013 | Label/config record targeting, local write constraints and service refusals, exact VPN enable/disable/default/advertised-route wire JSON in both clients and examples, actual DeviceDaemon fields, reported Parameter omissions and unchanged migration source authorization |
| FR-014, SC-006 | All four runnable examples, explicit environment configuration, every advertised flag and executed documentation snippets, inspectable partial failures and re-raised cancellation |
| FR-015 | Actual pinned SDK provenance/replay, network guard and zero-skip gate; excluded-API assertions; full existing daemon, file-upload, ConfigTree, Parameter and model-contract regressions |

All required implementation work is complete. The quality checklist markers were preserved. Live device validation remains optional supplemental evidence.


### Convergence completion: T065–T068

Both helpers now finish collecting the valid requested-device entries in a received batch before raising a foreign-device or conflicting-output contract error. The failure retains earlier output and empty output, preserves original target order, never overwrites conflicting output, and starts no further retrieval. Regressions cover both JSON key orderings in both helper modes.

Command response parsing now retains a separately validated job identity when an unambiguously job-shaped acknowledgment violates the requested execution mode. The mismatch remains a terminal contract failure, with the original response-validation cause and matching job identity in the failure and partial result. Real Client/AsyncClient MockTransport regressions verify the full path; legitimate string output keys named jid/minions and invalid job identities do not become job acknowledgments.

Deferred-mode failures also retain an unknown JID when a named output map can represent the requested jid device's output. Sixteen actual-client regressions cover direct submissions and both helpers, one-device and jid/minions output maps, and malformed acknowledgments with missing or invalid minions that still retain a known JID. Every case preserves cause chaining, one submission, no subsequent lookup, matching failure/outcome identities and caller command/context/transport ownership. Eight false-identity regressions failed before the T068 fix, while the eight malformed-acknowledgment controls passed; all sixteen now pass.

VPN wire regressions cover enabled VPN with omitted config, explicit disable, nested route defaults, explicit false and explicit true advertisement, typed actual Daemon results, unchanged context, and rejection of advertisement while disabling or of unrelated daemon settings before HTTP. Management example tests now assert their exact VPN request bodies as well.

The earlier red regression runs reproduced four key-order failures and three job-identity failures before their corresponding fixes. Final targeted and full-suite results are recorded in the acceptance table above. All 68 tasks, including the four convergence tasks, are complete; reviewer-owned checklist markers are unchanged.
