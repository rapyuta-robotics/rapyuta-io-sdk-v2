# Device Management Data Model

The implementation uses Pydantic v2 and the existing `SDKModel` conventions, with explicit aliases where a Python field differs from a wire key. New body models forbid unknown fields except named maps designed for user-defined keys. Responses validate known fields and retain permitted extensions as typed `JsonValue`, never `Any`. All public payload roots are named models. See [contracts/sdk.md](contracts/sdk.md) for routes, signatures, and envelope examples.

## Device identity and views

| Model | Fields / relationship | Validation and semantics |
| --- | --- | --- |
| `DeviceStatus` | NEW, REGISTERED, REJECTED, ONLINE, OFFLINE, DELETED, INITIALIZING, ERROR, FAILED | Read-state enum; not every read value can be externally submitted |
| `DeviceUpdateStatus` | REGISTERED, REJECTED, DELETED, INITIALIZING, ONLINE, OFFLINE, FAILED | Only externally permitted update states; server enforces valid transitions |
| `Device` | `uuid: str`, `name: str`, `status: DeviceStatus`; optional description, created_by, registration_time, last_online, last_status_update_time, `python_version` alias `device_version`, daemon status report, labels, config_variables, deployments, installation_metadata, error_code, error_message, reported OS/network fields | UUID is required remote identity; timestamps parse as datetime when supplied; detail collections are optional, preserving absence versus empty. Read Python version is a string, allowing historical devices; creation is Python 3 only |
| `DeviceDeployment` | io_deployment_id, deployment_id, phase, optional error_code and created_at | Read-only legacy deployment summary, not the v2 Deployment resource model |
| `DeviceDaemonReport` | Named root map of status/report values using `JsonValue` | Legacy daemon report may contain more than the newer structured DaemonStatus; retain reported data without exposing mutation |
| `DeviceSelectionRecord` | `uuid: str`, `id: int`, `name: str`, `status: DeviceStatus` | Positive numeric database ID must not be used as routing UUID |
| `DeviceListQuery` | Optional `name: str` | Exact backend name filter; no regex/all-online/architecture orchestration or invented pagination |

Known reported fields include host, username, saltversion, ip_interfaces, mac_addresses, and distribution/architecture details where present. Name each observed stable field with its actual wire type, using a named map for interface collections. Unknown platform-reported detail is preserved via a typed `__pydantic_extra__: dict[str, JsonValue]` on Device and nested extensible report models; do not fabricate missing fields or perform reads to fill them. Creation/update name validation is stricter than response decoding so historical data remains readable.

Device names use the backend pattern `^(?=.{3,256}$)[a-zA-Z]+[ \w-]*[^\W_-]$`, length 3–256. It permits spaces internally and Unicode word characters after initial ASCII letters. Description has maximum length 256. Initial registration can omit it or supply null; the inspected update handler discards empty/null values, so they do not clear an existing description. Names are unique per project/tenant among nondeleted devices, enforced by the service.

## Registration, onboarding, and update

| Model | Fields | Rules |
| --- | --- | --- |
| `DeviceCreate` | name; optional description; `config_variables: DeviceCreationConfig`; `labels: DeviceLabelsCreate` default empty; `python_version: Literal['3']` default '3' | Require an enabled docker or preinstalled runtime before submission; preserve the actual nested registration shape rather than synthesize v2 spec/metadata |
| `DeviceCreationConfig` | Named root `dict[str, StrictStr | StrictBool]` | Runtime keys runtime_docker/runtime_preinstalled accept strict bool or exact legacy strings 'True'/'False'; at least one true. Other values are strings; configuration-key validation applies. ROS distribution/workspace and arbitrary allowed keys remain nested; ignored historical server fields have no persistence promise |
| `DeviceUpdate` | Optional name, status: DeviceUpdateStatus, description | Require at least one explicitly set update field; reject explicitly null name. Preserve explicit description null/empty in the request, documenting that the server treats it as a no-op rather than clearing. Routing device ID is a scalar and is injected into a copied wire body; caller cannot provide/conflict with device_id |
| `DeviceTokenData` | `data: str` token (`repr=False`), device_id: str, script_command: str | Token string and sibling fields are required and nonempty; preserve exact token without installing it on the client. Suppress token in repr; documentation/fixtures use fake values |
| `DeviceMigration` | `project: str` | Explicit nonempty destination project; source project remains the call's context |

Backend state transitions are authoritative. Accepting a device means update status REGISTERED; rejecting means REJECTED. The SDK does not infer readiness from these acknowledgments. Migration checks online state, Python version, deployment activity, name collision, and permissions on the server; no prechecks or post-migration VPN workflow are added.

## Labels and configuration variables

| Model | Fields | Rules |
| --- | --- | --- |
| `DeviceLabel` | id: positive int, key: str, value: str | Immutable identity semantics for update/delete routing; key/value pattern `^[0-9a-zA-Z][a-zA-Z0-9_-]{0,49}$` |
| `DeviceLabelsCreate` | Named root string key/value map | Creates one or more labels in one platform operation; validate every key/value; empty default used only when initial device registration omits labels |
| `DeviceLabelUpdate` | Optional key and value | At least one explicitly supplied, nonnull field. Response is empty acknowledgment, not the edited label |
| `DeviceConfigVariable` | id: positive int, key: str, value: str, optional type: str/null | Strings on read; returned type is preserved when present |
| `DeviceConfigVariableCreate` | key: str, value: str | Key pattern `^[a-zA-Z_][a-zA-Z0-9_]{0,255}$`; value is nonempty. Runtime reserved values preserve service rules |
| `DeviceConfigVariableUpdate` | value: nonempty str | Does not rename a key; ID comes solely from the scalar route argument |

Label/config uniqueness is enforced per device. Configuration mutations require an online device; runtime cannot be renamed or deleted, and both runtime flags cannot be disabled. Existing-state restrictions belong to service responses, not hidden SDK reads. The default config listing has no internal typed-log/metric configuration selector.

## Device selection expressions

`DeviceSelection` has `operator: Literal['$and','$or']`, optional `labels: DeviceLabelExpression`, and optional `specs: DeviceSpecExpression`. Its JSON is the platform expression, not a translated SQL/filter language. Both filter branches omitted retain the backend's empty-selection behavior.

Use recursive named logical/leaf classes with a union distinguished by operator:

- Label logical nodes: operator $and/$or, args tuple of label expressions. The backend permits empty label logical arrays; retain its all/any semantics.
- Label leaves: operator $eq/$ne, args exactly `(field_name: str, value: str)`.
- Spec logical nodes: operator $and/$or, nonempty args tuple of spec expressions; reject empty spec logical arrays that the implementation cannot evaluate.
- Spec leaves: operator $eq/$ne/$in, args exactly `(field_name: str, value: JsonScalar)`. String $in means substring membership; nonstring operands do not match, as in the backend. Do not convert it to list containment.

For architecture compatibility, use explicit predicates: x86_64 or amd64 equality; armv7/aarch64 substring predicates. Specs filter online grain records; labels filter stored device labels including offline devices. No additional listing operation is embedded in selection.

## VPN and Parameter application

| Model | Fields | Rules |
| --- | --- | --- |
| `DeviceVPNUpdate` | Required strict `vpn: bool`; optional `config: DeviceVPNConfiguration` | Preserve false. Only VPN changes are expressible; reject unrelated keys and advertisement true when disabling |
| `DeviceVPNConfiguration` | `vpn: DeviceVPNRouteConfiguration` | Required nested VPN-only configuration, matching the wire shape |
| `DeviceVPNRouteConfiguration` | advertise_routes: strict bool default false | Boolean requests project-configured routes, never accepts subnet text. Omitted config defaults to no advertisement through service semantics |
| `DeviceVPNResponse` | Standard success envelope with response.data: existing `Daemon` | Actual kind DeviceDaemon, metadata/spec/status retained; no invented bool or convergence claim |
| `SSHCertConfig` | enable: strict bool | Add optional ssh_cert_config with alias sshcert_config to existing DaemonSpec to retain this observed response field. Do not change existing Daemon defaults or add a mutation method |
| Existing `AuthConfig` extension | auth: optional str, repr=False | Retain the downstream pull_secret.auth wire value using fake credentials in fixtures; keep existing fields/defaults unchanged |
| `DeviceParameterApply` | device_list: tuple[str,...], optional tree_names: tuple[str,...] | Nonempty unique device identifiers. Omitted/empty tree names mean all trees per service; no invented per-node workflow |
| `DeviceParameterApplyItem` | device_id: str, success: strict bool, optional error: str | Preserve each reported outcome; unknown requested IDs may be absent from response |

## Command request, responses, and waiting

| Model | Fields | Rules |
| --- | --- | --- |
| `DeviceCommand` | device_ids: tuple[str,...], cmd: str, optional shell/runas/cwd, env: string map default empty, bg: bool default false, run_async: bool default false, timeout: positive finite number default 300 | Nonempty unique identifiers, nonblank command, valid environment names. Preserve exact command/context and explicit defaults; no deprecated pwd alias or CLI shell wrapper |
| `DeviceCommandResultQuery` | device_ids: tuple[str,...] | Nonempty unique targets serialized as repeated singular device_id query keys |
| `DeviceCommandOutputs` | Named root `dict[str, StrictStr]` | Empty map allowed; empty output string differs from missing key. No implicit JSON-to-string coercion |
| `DeviceCommandJob` | jid: str, minions: tuple[str,...] | Nonblank opaque JID; deferred wire acknowledgment. Helpers validate unique accepted minions exactly match requested targets |
| `DeviceCommandSubmissionData` | Named validated root union of DeviceCommandOutputs / DeviceCommandJob | Client validates branch against requested execution mode; distinguish jid job shape from a device map with a coincidental key |
| `DeviceCommandPendingData` | error: literal 'Job not found or incomplete', data: DeviceEmptyData | Only the exact HTTP400 retrieval envelope produces pending |
| `DeviceCommandWaitOptions` | wait_timeout: positive finite float=300, poll_interval: positive finite float=10 | Immutable options; execution timeout stays in DeviceCommand |
| `DeviceCommandDeviceResult` | device_guid: str, output: str | Frozen per-device output, no invented process status |
| `DeviceCommandOutcome` | requested_devices: tuple[str,...], jid: str/null, responses: tuple[DeviceCommandDeviceResult,...], missing_devices: tuple[str,...] | Frozen ordered snapshot. Full success has no missing devices; partial snapshots may have none if responses arrived late |
| `DeviceCommandFailureStage` | validation, submission, retrieval, contract, incomplete_result, timeout, cancellation | String enum shared by ordinary failure, deadline expiry, and external cancellation context |
| `DeviceCommandFailure` | Required stage: DeviceCommandFailureStage, required message: nonempty str, jid: str/null default None, required requested_devices: tuple[str,...], required missing_devices: tuple[str,...] | Frozen context, no raw credentials, command environment, or exception objects in JSON. Underlying cause is chained on the exception |

Public failures are `DeviceCommandError`, `DeviceCommandTimeout`, `DeviceCommandCancelled`, and direct-operation `DeviceContractError`; inheritance and field access are specified in the SDK contract. Tuple-based outcome data is recursively immutable; freezing a model containing a mutable result dict would not provide that guarantee.

Every workflow exception pairs `.failure` and `.partial_result` from the same immutable snapshot: `failure.jid`, `failure.requested_devices`, and `failure.missing_devices` MUST exactly equal the corresponding `partial_result` fields. A known jid uses the command-job identifier validation, including safe single-segment routing. When a malformed acknowledgment still contains a valid jid, DeviceContractError retains that identity for the helper snapshot; None means unknown, never proof that submission was rejected. Identity tuples retain original target order. Required identity fields may be empty tuples only when no valid target identities are available, such as a preflight validation failure. Completed outputs are exposed only through `partial_result.responses`; causes are exposed through exception chaining, not duplicated in the failure payload.

Command state transitions:

```text
validated -> submit once -> immediate results -> complete before deadline
                         -> incomplete without job -> incomplete_result failure
                         -> deferred job -> retrieve remaining targets
                                            -> pending/partial -> wait -> retrieve
                                            -> all responses before deadline -> complete
                                            -> terminal error -> failure snapshot
                         -> deadline -> timeout snapshot
                         -> external async cancellation -> cancellation snapshot
```

Detached background launch remains an individual-operation outcome and is rejected by response-waiting helpers before submission. Repeated identical outputs preserve the original response; conflicting repeats, unexpected IDs, missing JID/minions, and mode mismatch are contract failures. An unobserved submission response means remote acceptance is unknown; never resubmit automatically.

Command serialization materializes timeout, bg, run_async, and env defaults even when not explicitly set; optional null shell/runas/cwd are omitted. Background mode takes precedence over deferred mode in the direct-operation response parser, matching service dispatch.

## Named response envelope inventory

Shared implementation bases may be generic, but public methods annotate concrete names:

| Response | Nested response type / data |
| --- | --- |
| DeviceListResponse | Named Device array data |
| DeviceResponse / DeviceUpdateResponse | Device |
| DeviceSelectionResponse | DeviceSelectionRecord array |
| DeviceRegistrationResponse / DeviceOnboardingResponse | DeviceTokenData, including sibling metadata |
| DeviceMutationResponse | DeviceEmptyData |
| DeviceLabelListResponse / DeviceLabelsCreateResponse | DeviceLabel array |
| DeviceConfigVariableListResponse | DeviceConfigVariable array |
| DeviceConfigVariableResponse | DeviceConfigVariable |
| DeviceVPNResponse | Daemon |
| DeviceParameterApplyResponse | DeviceParameterApplyItem array |
| DeviceCommandSubmissionResponse | DeviceCommandSubmissionData |
| DeviceCommandResultResponse | DeviceCommandOutputs |
| DeviceCommandPendingResponse | DeviceCommandPendingData with status error |

Success outer status is literal success. Pending is a deliberately separate error-status variant. Validate response shape before returning; do not accept false success statuses or error payloads as empty successful data.
