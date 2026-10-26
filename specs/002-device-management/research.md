# Device Management Research

## Evidence and scope

Research uses rio CLI revision `27bb77bb912705b58a5de0a2e99848dc023ba322`, SDK v1 revision `739a6fe44600ff0964fa56b04878ddb21e76b5be`, Device Manager revision `8123388760aca5b81adf903c24619d62705eb495`, and core/v2 server revision `4338812cda3502f7a2332bd6c6093fc491d179c2`. Local checkouts are respectively `/home/ankit/Projects/Work/rapyuta-io-cli`, `/home/ankit/Projects/Work/rapyuta-io-sdk`, `/home/ankit/Projects/Work/io_devel/device_manager`, and `/home/ankit/Projects/Work/rapyuta_io`. Device Manager command controller/model files also match the older `/home/ankit/Projects/Work/device_manager` revision `8ad00a015c45e599f3ae7b67f2adb96eac4d3b6e`.

Public reference documentation: [CLI Device commands](https://cli.rapyuta.io/device.html) and [SDK v1 Device module](https://sdk.rapyuta.io/device.html). Backing source and tests resolve discrepancies in old prose. Source paths below are relative to the identified checkouts; they describe verified snapshots, not a claim that every deployed environment has that revision.

All initial constitution gates pass. Research agents independently examined lifecycle/VPN contracts and command/deadline contracts. There are no unresolved design questions. The single timeout question raised during planning was answered and recorded in [spec.md](spec.md).

## R1 — Service routing and ownership

**Decision:** Reuse `Configuration.core_api_host`, resolved on each operation, and route through `/api/device-manager/v0`. Use the supplied client's existing HTTPX transport and `Configuration.get_headers`, including typed context overrides. Canonical controller paths avoid redirect dependence. Disable redirects on these service calls.

**Rationale:** Coreapi forwards body, query, headers, status, and response after stripping `/device-manager` from the public prefix. Parameter calls already resolve this host dynamically; no additional configuration setting is needed. Host absence raises the existing SDK `ValidationError` for Device operations only.

**Alternatives considered:** Guessing v2 lifecycle/command routes, adding a second host setting, caching the host at construction, or porting the v1 RestClient would duplicate configuration or change operation semantics.

**Evidence:** core server `pkg/coreapi/api/endpoint/endpoint.go:31-57`, `devicemanager.go:17-44`; SDK v1 `rapyuta_io/utils/settings.py:18-25,40,49-50`; current SDK `_parameter_api.py:32-38`, `config.py:100-157`.

## R2 — Typed legacy envelopes and errors

**Decision:** Named Pydantic response classes preserve `status` and nested `response.data`; onboarding also preserves sibling `response.device_id` and `response.script_command`. Empty JSON acknowledgments use a named empty model. API methods return typed acknowledgments when the platform supplies a body, following existing Parameter conventions. They return no fabricated Device or bool.

**Rationale:** Registration data is a token string, label update/delete data is `{}`, device update returns a summary, and configuration update returns a record. These are different contracts. Existing `handle_server_errors` maps status codes correctly but only extracts a top-level error; extend its error extraction compatibly to nested `response.error` while preserving current top-level behavior and exception categories. Service success status with an error envelope, invalid JSON, invalid status/envelope, and incompatible payloads are never accepted as success. HTTP 429 is terminal, using the existing unmapped-status error behavior; no automatic retry policy is introduced.

**Alternatives considered:** Unwrapping everything into raw dictionaries, constructing synthetic return records, changing existing HTTP exception classes, or allowing every HTTP400 through as pending would violate contracts or hide errors.

**Evidence:** Device Manager `utils/response_helper.py:132-155`, `utils/token_response.py:10-16`; `models/api/v0/labels.py:90-120`; current SDK `utils.py:56-74`, `_parameter_api.py:98-109`. [Pydantic models documentation](https://docs.pydantic.dev/latest/concepts/models/) describes validation and serialization; named strict inputs and explicit aliases will preserve wire data.

## R3 — Lifecycle, metadata, and selection

**Decision:** Implement 20 single-operation methods with identical names/signatures/models in both clients; the full matrix is in [contracts/sdk.md](contracts/sdk.md). Device summaries/details have a shared model with optional detail fields, while selection returns its own compact records. Scalar route identifiers stay scalar; request bodies and structured queries are named models.

**Rationale:** Names are project-unique among nondeleted devices. Creation requires at least one enabled runtime and the current service creates Python 3 devices. Preserve the actual device-name regex, including internal spaces and permitted Unicode characters. Read states include NEW and ERROR, but external updates accept only REGISTERED, REJECTED, DELETED, INITIALIZING, ONLINE, OFFLINE, FAILED. Transition eligibility stays server-authoritative. Get detail can fail HTTP400 when an online device becomes unavailable. Labels are a map on creation but records on reading; updating/deleting uses integer record IDs. Config records are string-valued and mutation is online-only. Parameter application can omit unknown devices; preserve its reported outcomes without synthesizing missing ones.

Selection is a POST operation with top-level `$and`/`$or`, optional labels/specs predicates, and recursive expressions. Labels support `$eq`/`$ne`; specs additionally support `$in`, which means substring membership for strings, not membership in an array. Specs operate on online devices; labels can match offline devices. Its numeric `id` is a database identity, separate from routing `uuid`.

**Alternatives considered:** Hidden architecture selection inside listing, accepting v1 Python 2 settings, using v2 resource metadata for legacy devices, fetching detail after every summary, key-based mutation lookup, or treating selection ID as a UUID would change reference behavior.

**Evidence:** Device Manager `models/devices.py:29-42,65-106`; `models/api/v0/devices.py:49-183,580-618,703-716,941-950`; `models/api/v0/auth_keys.py:91-99,119-123,188-191,326-365`; `models/labels.py:13-35`; `models/config_variables.py:14,44-62`; `models/api/v0/config_variables.py:20-27,47-77,95-104,113-138,295-327`; `models/api/v0/selection.py:52-119,147-255`; `models/api/v0/parameters.py:41-122`; CLI `riocli/device/util.py:193-210`.

Additional mutation details: `models/api/__init__.py:44-49` drops falsey update values, so empty/null descriptions do not clear stored metadata. Configuration create/update schemas require nonempty values (`api/v0/config_variables.py:64-74,205-216`), although stored read values may be empty. Canonical label listing ends with `/` (`api/v0/labels.py:239`), unlike label creation/mutations.

Compatibility limit: the inspected creation handler fixes version to 3 and does not persist every historical default config key, including legacy ROS settings. The SDK preserves supported submissions but must not promise the service persists ignored fields. Registration acknowledgment is not a readiness guarantee.

## R4 — VPN-only public control

**Decision:** Expose `set_device_vpn(device_guid, body: DeviceVPNUpdate, **kwargs)`. The typed payload contains required `vpn: bool` and optional VPN-only nested configuration with `advertise_routes: bool`. Enabling defaults route advertisement to false; disabling with route advertisement true is rejected locally. No arbitrary daemon or toggle-features method is added.

**Rationale:** One public request maps to the internal PATCH `/devices/{id}/daemons` operation and carries only VPN state/configuration. Device Manager calls `/internal/v2/devices/daemons/{id}/`; the v2 handler returns an updated daemon resource with kind `DeviceDaemon`. Device Manager wraps it under `response.data` and returns HTTP200. Use `DeviceVPNResponse` containing the existing `Daemon` response model. Add missing typed `DaemonSpec.ssh_cert_config` (wire alias `sshcert_config`) and `AuthConfig.auth` response fields, preserving existing defaults and accepting the actual kind supplied by the response. These response-model additions do not expose a daemon mutation interface.

**Alternatives considered:** Publishing generic daemon PATCH, synthesizing a boolean acknowledgment, sending project subnet strings, or polling VPN readiness is outside the user's scope.

**Evidence:** CLI `riocli/device/vpn.py:128-132`; Device Manager `models/api/v0/devices.py:186-285,341-358`, `utils/v2_client.py:61,280-323`; core/v2 `v2/cmd/apiserver/main.go:1562-1567`, `v2/devices/server/http.go:233-261`, `v2/api/extensions/daemons.go:23-96`, `v2/devices/dao/daemon.go:48-78`; current SDK `models/daemons.py:109-177`. Actual spelling is `advertise_routes`; historical Swagger's `advertised_routes` is incorrect. Missing service/device, readiness refusals, and downstream errors preserve SDK exception mapping; already-enabled/disabled binding cases follow backend idempotence.

Core/v2 `v2/api/extensions/common.go:24-29` defines pull-secret `AuthConfig` with registry and auth fields; the existing SDK omits auth. Preserve the actual response's encoded credential field with `repr=False` and fake fixture content. Existing optional username/password fields remain compatible rather than being removed.

## R5 — Commands and exact pending recognition

**Decision:** Submit with POST `/cmd/`; retrieve with GET `/cmd/{jid}` and repeated `device_id` query keys. Immediate results are device-ID-to-string maps; deferred results contain an opaque `jid` and `minions` list; background results acknowledge launch with strings such as `SUCCESS`. Result retrieval has a typed successful-results variant and an exact typed pending variant.

Only HTTP400 with `status=error`, `response.error="Job not found or incomplete"`, and empty `response.data` is pending. Interpret that condition before shared HTTP error handling on retrieval only. Submission errors and all other lookup errors are terminal. The service conflates nonexistent and incomplete jobs, so callers cannot distinguish them until the waiting deadline. JIDs are opaque nonblank strings and encoded as a safe path segment, not numeric timestamps.

**Rationale:** Salt job retrieval projects only each device's `return`; it does not expose exit codes or separate output streams. Empty strings count as received results. Direct client calls never poll. For submissions, the requested run_async/background mode determines the expected response variant; malformed variant transitions are rejected.

Command serialization explicitly emits timeout=300, bg=false, run_async=false, and env={} defaults while omitting optional null shell/runas/cwd, matching SDK v1 `Command.to_json`; the service forwards supplied kwargs and does not establish the 300-second default itself. `bg=true` takes precedence over run_async and produces launch acknowledgments, not a job (`models/api/v0/cmd.py:55-58`). Helpers reject bg before HTTP.

**Alternatives considered:** A rich invented execution model, copying the ignored legacy `jid` query, polling all HTTP400 responses, or recognizing any map with a key named `jid` without validating its structure would misrepresent the service.

**Evidence:** Device Manager `api/v0/cmd.py:22-28,121-129,180-184`, `models/api/v0/cmd.py:42-94`, `impl/config_manager/saltstack/base.py:266-318,793-802`; service tests `tests/api/v0/cmd_tests.py:244-271`, `tests/impl/saltstack_tests.py:208-259`. SDK v1 `rapyuta_io/clients/device.py:589-605` only reads its first device and counts sleep duration; CLI `riocli/device/execute.py:178-211` retries in batches. These algorithms are not copied.

## R6 — Waiting deadline and async cancellation

**Decision:** The user selected existing synchronous transport semantics. Use elapsed monotonic time, stop starting requests/sleeps after the deadline, and pass the remaining budget through an optional command-call `request_timeout` cap. Cap each existing connect/read/write/pool timeout separately; replace unlimited components with the cap without mutating client defaults. A sync request already started may finish late; merge its valid known results into partial context and then raise timeout, even if all devices have responded. A malformed or terminal late response remains a failure with its underlying cause, not a false success.

Async uses the same budget/cap plus `asyncio.timeout_at` around the waiting workflow. Distinguish its own deadline expiry from external cancellation; external cancellation raises a `CancelledError` subclass with typed partial context. All paths leave the caller's client open. No worker thread, replacement transport, retry, remote cancellation, or discarded background process is used.

**Rationale:** [HTTPX timeout documentation](https://www.python-httpx.org/advanced/timeouts/) defines separate operation/inactivity limits, not a total request duration. [Python 3.13 asyncio documentation](https://docs.python.org/3.13/library/asyncio-task.html#timeouts) provides cancellable timeout contexts and describes propagation of cancellation. The spec's FR-008 and SC-005 were updated with the user's answer before final design.

**Alternatives considered:** Claiming request timeout is a total deadline, joining a timed-out worker that leaves I/O running, interrupting pooled sockets, or replacing the caller's transport was rejected. None preserves a portable strict sync deadline and existing ownership/transport behavior.

## R7 — Separate helper state and outcomes

**Decision:** Put sync/async command helpers in `helpers/device.py` and `helpers/async_device.py`, with pure shared bookkeeping in `helpers/_device_command.py`. Use immutable tuple-based result/failure models, keeping response strings in request-target order. Helpers copy/revalidate supplied commands; fill CLI helper defaults root and /bin/bash only where omitted. Immediate execution remains default, deferred is explicit, background is rejected by helpers.

Deferred helpers submit once, validate expected accepted minions, retain job identity, and query remaining targets. Valid partial maps accumulate. Duplicate identical results are harmless; conflicting results for an already completed device are a contract failure. Unexpected devices and malformed acknowledgments are contract failures. Job acknowledged with missing minions fails with job/target context rather than silently narrowing targets.

**Alternatives considered:** Mutable shared response dictionaries, truthiness-based completion, CLI output printing, a client-owned multi-operation execute-and-wait method, or silently dropping unavailable targets violates scope or completion rules.

## R8 — Verification and regressions

**Decision:** Use real JSON/schema fixtures derived from pinned source/test snapshots and HTTPX MockTransport. Verify request envelopes, exact paths/verbs/query multiplicity, repeated serialization, per-mode signatures/results/errors, each metadata operation, VPN's restricted payload, and every command state transition. Add replay comparison against actual pinned v1 request serialization for compatible public operations; explicitly account for canonical slash handling and deliberately corrected helper behavior. No live credentials or skipped reference cases substitute for required fixture compatibility. [HTTPX transport documentation](https://www.python-httpx.org/advanced/transports/#mock-transports) supports deterministic transport fixtures.

Regression checks cover nested and top-level error extraction, existing daemon reads and added response field, file uploads, Parameter operations/helpers, model discovery, and existing public exports. Implementation must pass Ruff 0.16.9 and the repository's Python 3.13+ test environment. This phase writes design documents, not implementation or passing implementation-test claims.
