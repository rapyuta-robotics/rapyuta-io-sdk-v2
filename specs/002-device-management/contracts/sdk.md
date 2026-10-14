# Device SDK Contracts

These are the implemented public contracts. All methods below exist on both `Client` and `AsyncClient`; the latter is awaitable and has identical arguments/defaults and response types. Existing methods remain unchanged. Models are exported through `rapyuta_io_sdk_v2.models` and the package's existing root-export convention. Workflow helpers are exported through `rapyuta_io_sdk_v2.helpers`.

## Common conventions

- Scalar `device_guid` is the remote UUID/string identifier, never a device name or a numeric selection ID. Nonblank route identifiers are encoded as single safe path components; `/`, `\\`, traversal-only values, and control characters are rejected rather than interpreted as routes.
- Label/config IDs are strict positive integers. JIDs are opaque nonblank strings using the same safe routing rules; no timestamp-format requirement.
- `body` is a named Pydantic model, not a raw dict. Structured list/retrieval queries use named query models. Revalidate before serialization using aliases and JSON mode. Partial updates and other omission-sensitive bodies use `exclude_unset=True`, preserving explicitly supplied false, empty strings, and supported nulls. Command bodies explicitly serialize operational defaults (`timeout=300`, `bg=false`, `run_async=false`, `env={}`) even when the caller omits them; omit null/unset optional shell, runas, and cwd. Do not rely on an undocumented server timeout default.
- Each method accepts `**kwargs: Unpack[HeaderOptions]`, preserving existing authentication/context header behavior. The two command methods instead use `DeviceCommandCallOptions`, an extension with optional `request_timeout: float`. It is a positive finite cap in seconds for individual network operations, not a total request deadline; omission preserves configured HTTPX timeouts. Separate it before `get_headers`, cap each configured connect/read/write/pool timeout, and leave client defaults untouched.
- Methods perform exactly one HTTP operation. No automatic authentication, key lookup, refresh, listing, architecture filtering, retries, polling, or readiness waits.
- JSON responses retain `.status` and `.response.data`. Each envelope is a named model. Mutations with `{}` data return `DeviceMutationResponse` with a named `DeviceEmptyData`; they do not invent updated records. This follows existing typed Parameter acknowledgment behavior even though some v2 resource deletes have no response body and return `None`.
- Shared HTTP exceptions preserve existing SDK mappings and nested Device Manager error messages. Pydantic validation remains distinguishable from HTTP failures. Device envelope/protocol mismatches raise `DeviceContractError`, an SDK `UnknownError` subtype. Its message does not dump request credentials or command environments. A malformed deferred acknowledgment can retain a separately validated jid, which the helper transfers into its failure snapshot. The VPN response reuses Daemon with additive typed ssh_cert_config (alias sshcert_config) and pull_secret.auth fields so observed server data is retained.

## Client methods and wire matrix

`H` below means `**kwargs: Unpack[HeaderOptions]`. `C` means `**kwargs: Unpack[DeviceCommandCallOptions]`. Paths are relative to `${Configuration.core_api_host}/api/device-manager/v0`. Canonical slash spelling is intentional; redirects are disabled.

| Public signature (excluding self) | Method and path | Request | Return model / response.data |
| --- | --- | --- | --- |
| `list_devices(*, query: DeviceListQuery | None = None, H)` | GET `/devices/` | Optional `name` query; no body | `DeviceListResponse` / device array |
| `select_devices(body: DeviceSelection, H)` | POST `/selection/query` | Recursive selection model | `DeviceSelectionResponse` / compact selection-record array |
| `get_device(device_guid: str, H)` | GET `/devices/{device_guid}` | No body | `DeviceResponse` / available device detail |
| `create_device(body: DeviceCreate, H)` | POST `/auth-keys/` | Registration model; `download_type=script` query as v1 | `DeviceRegistrationResponse` / token string, with sibling device ID and script command |
| `get_device_onboarding(device_guid: str, H)` | GET `/auth-keys/{device_guid}/token/` | No body | `DeviceOnboardingResponse` / same token envelope |
| `update_device(device_guid: str, body: DeviceUpdate, H)` | PUT `/devices/` | Copy of submitted body plus wire `device_id` from route argument | `DeviceUpdateResponse` / summary |
| `delete_device(device_guid: str, H)` | DELETE `/devices/{device_guid}` | No body | `DeviceMutationResponse` / `{}` |
| `list_device_labels(device_guid: str, H)` | GET `/labels/{device_guid}/` | No body | `DeviceLabelListResponse` / label array |
| `create_device_labels(device_guid: str, body: DeviceLabelsCreate, H)` | POST `/labels/{device_guid}` | Flat key/value map | `DeviceLabelsCreateResponse` / created label array |
| `update_device_label(label_id: int, body: DeviceLabelUpdate, H)` | PUT `/labels/{label_id}` | Submitted `key` and/or `value` | `DeviceMutationResponse` / `{}` |
| `delete_device_label(label_id: int, H)` | DELETE `/labels/{label_id}` | No body | `DeviceMutationResponse` / `{}` |
| `list_device_config_variables(device_guid: str, H)` | GET `/config_variables/device/{device_guid}/` | No body; default configuration view | `DeviceConfigVariableListResponse` / record array |
| `create_device_config_variable(device_guid: str, body: DeviceConfigVariableCreate, H)` | POST `/config_variables/device/{device_guid}` | `key`, `value` | `DeviceConfigVariableResponse` / created record |
| `update_device_config_variable(config_id: int, body: DeviceConfigVariableUpdate, H)` | PUT `/config_variables/{config_id}` | `value`; no caller-supplied route ID in body | `DeviceConfigVariableResponse` / updated record |
| `delete_device_config_variable(config_id: int, H)` | DELETE `/config_variables/{config_id}` | No body | `DeviceMutationResponse` / `{}` |
| `set_device_vpn(device_guid: str, body: DeviceVPNUpdate, H)` | PATCH `/devices/{device_guid}/daemons` | Restricted VPN payload | `DeviceVPNResponse` / updated `Daemon` resource |
| `apply_device_parameters(body: DeviceParameterApply, H)` | POST `/parameters/` | `device_list`, optional `tree_names` | `DeviceParameterApplyResponse` / reported per-device outcomes |
| `execute_device_command(body: DeviceCommand, C)` | POST `/cmd/` | Exact command/options/targets | `DeviceCommandSubmissionResponse` / result map or deferred acknowledgment |
| `get_device_command_result(jid: str, *, query: DeviceCommandResultQuery, C)` | GET `/cmd/{jid}` | Repeated `device_id` query; no body | `DeviceCommandResultResponse` or `DeviceCommandPendingResponse` |
| `migrate_device(device_guid: str, body: DeviceMigration, H)` | PUT `/devices/{device_guid}/migrate` | `project` destination | `DeviceMutationResponse` / `{}` |

Twenty public methods cover the complete clarified operation inventory. Do not add `get_all_devices`, mutable v1 Device actions, generic `patch_daemons`/`toggle_features`, topic methods, agent upgrade, deprecated metric operations, or fleet-wide VPN actions.

## Examples of wire payloads

Registration:

```json
{"name":"robot-alpha","config_variables":{"runtime_docker":true,"ros_workspace":"/home/rapyuta/catkin_ws"},"labels":{"fleet":"alpha"},"python_version":"3"}
```

Current server always creates Python 3; `python_version="3"` is retained for reference-compatible submission, not a selector for other versions. Some legacy default config keys are ignored by the current server; no persistence guarantee is made for ignored historical fields.

Device update uses its scalar identifier without a prior read:

```json
{"device_id":"device-a","description":"Warehouse robot"}
```

The inspected server drops falsey update values: empty/null descriptions are submitted faithfully but are no-ops, not a clearing operation. Configuration create/update values must be nonempty strings even though stored configuration records can contain empty strings.

VPN enable with route advertisement disabled:

```json
{"vpn":true,"config":{"vpn":{"advertise_routes":false}}}
```

Omitting `config` retains the service's false default. Explicit `vpn=false` must be serialized, not dropped. An enabling request may set advertisement true; disabling with advertisement true is invalid. The API does not accept caller-provided project subnet strings or unrelated daemon keys.

Command:

```json
{"device_ids":["device-a","device-b"],"cmd":"printf 'ready\\n'","shell":"/bin/bash","runas":"root","env":{},"cwd":"/home/rapyuta","timeout":300,"run_async":true,"bg":false}
```

No shell wrapping, command quoting changes, local execution, or environment logging occurs.

Submission response mode follows backend precedence: `bg=true` returns launch-output acknowledgments regardless of `run_async`; otherwise `run_async=true` returns a job, and immediate mode returns output. Helpers reject background before submission.

## Envelope examples and parsing

Immediate command success:

```json
{"status":"success","response":{"data":{"device-a":"ready\n","device-b":""}}}
```

Deferred acknowledgment:

```json
{"status":"success","response":{"data":{"jid":"job123","minions":["device-a","device-b"]}}}
```

Retrieval queries retain multiplicity: `?device_id=device-a&device_id=device-b`. Do not send a redundant `jid` query. Retrieve only unresolved requested devices in helper workflows; direct callers control their query.

Exact pending response, **retrieval HTTP400 only**:

```json
{"status":"error","response":{"error":"Job not found or incomplete","data":{}}}
```

`DeviceCommandPendingResponse` has `status="error"` and a nested literal message plus named empty data, so callers can distinguish it from successful empty maps. No ordinary terminal HTTP failure is turned into this model. In particular, `Device offline`, `invalid device_ids`, an empty device list, changed message, nonempty pending data, malformed JSON, and pending text on submission are failures. The service does not distinguish unknown jobs from incomplete jobs.

Registration/onboarding envelope:

```json
{"status":"success","response":{"data":"example-token","device_id":"device-a","script_command":"sudo bash start -r dockercompose"}}
```

The token remains exact string data with `repr=False`; documentation and fixtures use fake tokens. It is not an auth token installed on the supplied client. Consumers retrieve the separately issued script; SDK helpers do not install or run it.

## Public helpers

```text
execute_device_command(client: Client, body: DeviceCommand, *,
    options: DeviceCommandWaitOptions | None = None,
    **kwargs: Unpack[HeaderOptions]) -> DeviceCommandOutcome

execute_device_command_async(client: AsyncClient, body: DeviceCommand, *,
    options: DeviceCommandWaitOptions | None = None,
    **kwargs: Unpack[HeaderOptions]) -> DeviceCommandOutcome
```

The helper import location distinguishes it from the one-operation client method. `options=None` selects `wait_timeout=300`, `poll_interval=10`. Remote command execution timeout comes from `body.timeout`, default 300. Helper-only unspecified shell/user defaults become `/bin/bash` and `root` on a validated copy; explicit values, empty output, command text, environment, working directory, and requested immediate/deferred mode are preserved. `bg=True` is rejected before HTTP; `run_async` is not a choice between these two helper entry points.

1. Validate options and a copied command; start one monotonic budget covering validation completion, submission, retrieval, and sleep. Record original target order. Never mutate `body` or caller/client settings.
2. Submit exactly once with capped network-operation timeouts. If all immediate outputs arrive before the deadline, return them. If an immediate response is incomplete without a JID, raise an incomplete-result error. A deferred response requires a valid JID and exactly the accepted requested minions, without duplicates; a mismatch is a contract failure retaining a known JID.
3. For a deferred job, retrieve unresolved devices immediately, then sleep at most `min(poll_interval, remaining)` between pending/partial batches. Merge only requested device outputs. Completion depends on keys, not truthiness. Repeated identical responses are harmless; conflicting repeats and unexpected devices fail the contract. Preserve earlier output.
4. Check the deadline before each request/sleep and after each response. A valid late synchronous response may enrich partial context, but cannot produce success; raise `DeviceCommandTimeout`. Terminal/malformed responses preserve their cause even if late. A shorter transport timeout before the overall deadline is a retrieval/submission failure; do not retry it as pending.
5. Async additionally wraps the workflow in `asyncio.timeout_at(loop.time()+wait_timeout)`. Internal deadline expiry produces `DeviceCommandTimeout`; external cancellation produces `DeviceCommandCancelled`. Do not shield work, consume cancellation, launch extra requests during cleanup, or use synchronous I/O.
6. Return responses as immutable `DeviceCommandDeviceResult` tuples in original target order. Errors carry a snapshot outcome and unresolved target tuple. Remote commands may still run after local timeout/cancellation. The supplied client remains open.

## Failures and partial progress

- `DeviceCommandError(Exception)`: `.failure: DeviceCommandFailure`, `.partial_result: DeviceCommandOutcome`, chained original cause where available.
- `DeviceCommandTimeout(DeviceCommandError, TimeoutError)`: same context; distinguishes the waiting deadline from a shorter transport timeout.
- `DeviceCommandCancelled(asyncio.CancelledError)`: same typed context; caller should inspect and re-raise.
- `DeviceContractError(UnknownError)`: invalid platform result shape, mismatched mode, or unexpected IDs. Direct client methods raise this without helper bookkeeping; helpers wrap it as a contract-stage `DeviceCommandError`.

`DeviceCommandFailure` has the following stable public fields:

| Field | Type / default | Meaning |
| --- | --- | --- |
| stage | Required DeviceCommandFailureStage | validation, submission, retrieval, contract, incomplete_result, timeout, or cancellation |
| message | Required nonempty str | Failure description without raw credential or command-environment contents |
| jid | str or None; default None | Known validated job identifier, otherwise unknown |
| requested_devices | Required tuple[str,...] | Known original targets in request order |
| missing_devices | Required tuple[str,...] | Targets without collected responses, in request order |

The three identity fields exactly match `partial_result.jid`, `partial_result.requested_devices`, and `partial_result.missing_devices` on the same exception. Empty identity tuples are allowed when validation has no valid targets to record. Completed outputs remain in `partial_result.responses`, and an underlying cause is chained when available rather than serialized into `.failure`.

A timeout/cancellation during submission may have no known JID; it must not claim the command was never accepted remotely. No automatic retry, rollback, remote cancellation, or resubmission is performed.

## Compatibility gates

Tests must assert one platform request for every client call, matching sync/async signatures/defaults/models/errors, no excluded public methods, correct typed header overrides, all 20 route contracts, fake-token handling, and exact pending recognition. Reference replay compares actual pinned SDK v1 public serialization where its public contract exists. Server fixtures establish corrected/slash-sensitive routes, migration, and multi-device polling behavior. HTTPX MockTransport and clock controls keep these tests isolated; live verification is supplemental.
