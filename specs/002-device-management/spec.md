# Feature Specification: Device Management and Command Responses

**Feature Branch**: `feat/device`

**Created**: 2026-10-14

**Status**: Draft

**Input**: User description: "Add support for Device Management API in the Client and AsyncClient. Add a higher-level helper for execute command and get response. References: rio CLI; rapyuta-io-sdk (v1)."

## Clarifications

### Session 2026-10-14

- Q: Should deprecated topic operations be supported? → A: No. Exclude listing topics, reading topic status, subscribing, and unsubscribing from both clients and this feature.
- Q: Should agent-upgrade requests be supported? → A: No. Agent upgrade is deprecated and excluded from both clients and this feature.
- Q: What should replace the internal device daemon-change interface? → A: Expose device VPN enable/disable in both clients, with optional route advertisement when enabling; do not expose a generic daemon-change interface.
- Q: Which public conventions should the new Device methods follow? → A: Use the existing Client and AsyncClient conventions for names, arguments, typed payloads/results, context overrides, validation, errors, and synchronous/asynchronous parity.
- Q: How should the command helper's wait limit behave when a synchronous network request is already in progress? → A: Use existing transport semantics: stop polling at the wait deadline and bound network operations by the remaining budget; a request already in progress may finish later.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage devices throughout their lifecycle (Priority: P1)

An operator using the SDK can discover devices in a project, inspect a device, register a new device, retrieve its onboarding authorization, update its details or acceptance state, and delete it. Synchronous and asynchronous applications have the same capabilities.

**Why this priority**: Device identity, registration, and discovery are prerequisites for device-specific management workflows.

**Independent Test**: Exercise discovery, selection, registration, onboarding authorization, inspection, update, and deletion against controlled reference responses in both client modes. Verify identities, submitted values, returned details, and rejected operations.

**Acceptance Scenarios**:

1. **Given** a project containing online and offline devices, **When** an operator lists devices or submits a selection expression, **Then** the response preserves platform identities, state, and matching behavior; an empty match returns an empty collection.
2. **Given** a device identifier, **When** the operator inspects the device, **Then** available identity, runtime, configuration, labels, reported system information, and failure details are accessible through validated named contracts, without additional hidden reads.
3. **Given** valid registration details including runtime options, configuration variables, and labels, **When** the operator registers a device and separately retrieves onboarding authorization, **Then** the created identity and platform-provided token and script command are available without running an installer locally or on the device.
4. **Given** an existing device, **When** the operator updates its name, description, or acceptance state, **Then** only requested values are submitted and the platform acknowledgment is preserved.
5. **Given** a device that can be deleted, **When** deletion is requested, **Then** the platform acknowledgment is returned; a missing device or deployment-related refusal is surfaced without deleting deployments automatically.
6. **Given** an unauthorized project, an invalid registration, or a nonexistent device, **When** an operation is attempted, **Then** validation and platform errors remain distinguishable from successful empty results.
7. **Given** an application already using existing resource methods, **When** it invokes a new Device method in either client mode, **Then** operation naming, scalar identifier and typed body conventions, applicable per-call context overrides, returned models, and shared error categories follow the same conventions; asynchronous counterparts differ only in requiring awaiting.

---

### User Story 2 - Submit commands and retrieve their results explicitly (Priority: P1)

An application can submit a command to specified devices and inspect the immediate response or job identifier. It can retrieve an existing job's results separately, retaining control over when it waits.

**Why this priority**: Explicit command operations are useful independently and provide the foundation for the requested convenience helper.

**Independent Test**: Submit immediate and deferred commands and retrieve known jobs with both clients. Verify command options, targeting, job identity, output preservation, and one platform operation per client call.

**Acceptance Scenarios**:

1. **Given** one or more device identifiers and a valid command, **When** immediate execution is requested, **Then** submission returns the platform response associated with each responding device, preserving multiline and empty output.
2. **Given** deferred execution is requested, **When** the command is submitted, **Then** submission returns its job identifier without automatically waiting for completion.
3. **Given** a job identifier and requested device identifiers, **When** results are retrieved, **Then** the call returns available device results or the platform's pending indication without repeated retrievals of its own.
4. **Given** supplied shell, user, environment variables, working directory, execution timeout, and background/deferred flags, **When** a command is submitted, **Then** their meanings match the reference operation and command text is preserved without an added shell wrapper.
5. **Given** the platform accepts a background launch, **When** its response is read, **Then** the acknowledgment is represented as a launch outcome without claiming the detached process has completed.

---

### User Story 3 - Execute a command and receive all requested responses (Priority: P1)

An operator can make one helper invocation to execute a command on one or more devices and obtain results, without writing submission, waiting, or aggregation logic. The outcome identifies every requested device, including devices still missing when the operation fails or times out.

**Why this priority**: This directly delivers the requested higher-level workflow and removes repeated command-response bookkeeping from applications.

**Independent Test**: Run the helper with immediate results and a deferred job whose three devices respond at different times. Inject timeout, submission failure, retrieval failure, and asynchronous cancellation, verifying preserved partial results and no duplicate submissions.

**Acceptance Scenarios**:

1. **Given** an immediate command with responses for every requested device, **When** the helper is invoked, **Then** it returns those responses without further result retrieval.
2. **Given** a deferred command whose devices respond in successive batches, **When** the helper is invoked, **Then** it submits once, waits for the same job, retains earlier responses, and succeeds only after all requested devices have responses.
3. **Given** a response containing an empty output string for one requested device, **When** results are aggregated, **Then** that device counts as having responded and its empty output is preserved.
4. **Given** only some devices respond within the wait limit, **When** that limit expires, **Then** the helper raises a timeout carrying the job identifier when known, completed responses, and missing device identifiers; partial completion is not returned as whole-operation success.
5. **Given** a permission failure, transport failure, or malformed response during retrieval, **When** the helper encounters it, **Then** it stops and exposes the cause and known partial outcome without treating the failure as pending or resubmitting the command.
6. **Given** an asynchronous helper is waiting, **When** another asynchronous task runs or the caller cancels the wait, **Then** other work remains responsive, cancellation is preserved with known job and partial-result context, and no further submissions or retrievals begin after cancellation.
7. **Given** a detached background command or invalid helper options, **When** the response-waiting helper is invoked, **Then** it rejects the request before submission and explains that detached process completion is unavailable through this workflow.

---

### User Story 4 - Configure and operate existing devices (Priority: P2)

An operator can manage labels and configuration variables, enable or disable VPN on a specified device, apply Parameter trees, and migrate a device to another project through either client mode.

**Why this priority**: These operations complete the bounded Device Management scope after lifecycle and command support are available.

**Independent Test**: Exercise each operation category with controlled success and rejection responses. Read back labels and configuration variables, and check per-device outcomes where the platform reports them.

**Acceptance Scenarios**:

1. **Given** an existing device, **When** an operator lists, creates, updates, and deletes labels or configuration variables, **Then** record identifiers, keys, and values are preserved and duplicate-key or missing-record errors remain visible.
2. **Given** a device identifier and a requested VPN state, **When** the operator enables or disables VPN, **Then** one operation submits the explicit VPN state and applicable route-advertisement choice for that device, preserves the platform acknowledgment or refusal, and changes no unrelated daemon settings.
3. **Given** VPN is being enabled, **When** route advertisement is explicitly requested, **Then** the operation requests advertisement of project-configured subnets; without that option, route advertisement defaults to disabled.
4. **Given** a missing device, an invalid VPN payload, or insufficient permission, **When** VPN control is attempted, **Then** the failure follows the same validation and platform-error conventions as other client methods, without reporting success or choosing another target.
5. **Given** selected devices and optional Parameter tree names, **When** the operator applies Parameters, **Then** the platform receives the exact targets and tree selection and all reported per-device successes and failures are available. Omitting tree names retains the reference's all-trees behavior.
6. **Given** a device eligible for migration, **When** the operator requests migration to a specified project, **Then** the operation's acknowledgment or refusal is available without automatically waiting for readiness or configuring VPN.

### Edge Cases

- Listing or selection finds no devices: return an empty collection rather than a not-found error.
- A command target list is empty, contains empty identifiers, or contains duplicates: reject before submission; never interpret it as all devices. Helpers accept explicit identifiers, not names or regular expressions.
- Blank command text, invalid environment-variable names, or nonpositive/nonfinite execution timeout, wait timeout, or polling interval: reject before submission. Helper defaults are a 300-second wait limit and a 10-second polling interval; command execution timeout is a separate setting.
- A device becomes offline, is deleted, or moves projects after submission: preserve any platform-reported outcome; a missing response remains unresolved until a terminal failure or the wait deadline.
- Successful result retrieval contains only a subset of requested devices: retain those responses and continue waiting for the remainder. Repeated results do not erase already collected output; unrelated device identifiers are a contract error.
- An empty result collection or explicit pending response is not proof of completion. A nonempty job identifier is required for deferred responses; a missing identifier is a contract error.
- Immediate submission omits a requested device and supplies no job identifier: report incomplete results with completed and missing devices rather than inventing a job or resubmitting.
- Output may be empty, multiline, Unicode, or contain command failure text. Preserve it exactly; do not infer success, exit status, or separate output streams that the platform does not report.
- A detached background launch may acknowledge success before the process exits. It remains available through the individual command operation and is rejected by the response-waiting helper.
- Deadline expiration or cancellation stops local waiting; it does not cancel the remote command. Retain a known job identifier for later explicit retrieval.
- Authentication, authorization, job-not-found, service, and invalid-response errors are failures unless the reference contract explicitly identifies the response as pending.
- Labels and configuration variables use returned record identifiers for update/delete. Key-based lookup is caller-controlled and does not add hidden client operations.
- VPN control requires one explicit nonempty device identifier; it never defaults to every device, modifies tracing or other daemon features, configures project subnets, or waits for VPN readiness. An acknowledgment confirms the requested change was accepted, not that connectivity is established.
- Registration, migration, and VPN-change acknowledgments are not readiness guarantees. Existing daemon reads, file-upload operations, shared URLs, and deployment operations continue to behave as before.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `Client` and `AsyncClient` MUST provide equivalent coverage of the following operation set. Each individual method MUST perform one platform operation, preserve its semantics, and document inputs, outputs, and failure behavior. New methods MUST follow comparable existing client naming and argument conventions, including operation-oriented snake_case names, scalar routing identifiers, and a typed `body` argument for request payloads. Corresponding synchronous and asynchronous methods MUST have the same public names, arguments, defaults, and result models; only asynchronous invocation requires awaiting.

  | Operation | Input contract | Response contract |
  | --- | --- | --- |
  | List devices | Project context and optional reference-supported name filter | Device summaries, including identity and state |
  | Select devices | Validated platform selection expression, including architecture predicates | Matching device records |
  | Get device | Device identifier | Full device details available from the platform |
  | Register device | Name, description, runtime settings, Python/ROS settings, labels, and configuration variables | Registration response and created identity |
  | Get onboarding authorization | Device identifier; no body | Onboarding token and script command |
  | Update device | Device identifier and submitted detail/state changes | Platform update acknowledgment |
  | Delete device | Device identifier; no body | Platform deletion acknowledgment or refusal |
  | List/create/update/delete labels | Device identifier for list/create; label record identifier for update/delete; validated key/value payload where applicable | Label records or mutation acknowledgment |
  | List/create/update/delete configuration variables | Device identifier for list/create; variable record identifier for update/delete; validated key/value payload where applicable | Configuration records or mutation acknowledgment |
  | Enable/disable device VPN | One device identifier and validated VPN state; optional route advertisement when enabling | Platform VPN-change acknowledgment or refusal |
  | Apply Parameters | Explicit device identifiers and optional tree names | Reported per-device success and error outcomes |
  | Submit command | Explicit device identifiers and validated command/options | Immediate per-device results or deferred job acknowledgment |
  | Get command results | Job identifier and requested device identifiers; no body | Available per-device results or explicit pending indication |
  | Migrate device | Device identifier and destination project | Platform migration acknowledgment or refusal |

- **FR-002**: Device Management operations MUST use the supplied client's authentication, environment, and project context, honor the existing typed per-call authentication/context keyword overrides through the supplied client configuration, and support an explicitly configured service location. Device service configuration MUST preserve existing resource routing. Migration MUST use source context for authorization and MUST NOT silently change the client's selected project.
- **FR-003**: New Device methods MUST follow existing payload-model validation, snake_case field naming, explicit wire-alias, return-model, and SDK error conventions. Shared HTTP failures MUST use the existing SDK exception categories; device-specific details MUST be preserved without substituting v1 exception classes. All public request and response payloads MUST have validated named model contracts covering the records, requests, acknowledgments, and outcomes listed in FR-001. Contracts MUST preserve platform field meanings, identifiers, response envelopes, and omitted versus explicitly supplied values. Missing optional detail in a summary MUST NOT trigger an automatic detail fetch. Operations without request or response payloads MUST document that absence.
- **FR-004**: Command contracts MUST support command text, target devices, shell, execution user, environment variables, working directory, execution timeout, deferred execution, and detached background execution. Explicit options and text MUST retain their reference meanings; background execution and deferred result retrieval MUST remain distinct from the choice of synchronous or asynchronous client.
- **FR-005**: Individual command submission and result retrieval MUST remain independently usable. Submission MUST return its immediate outcome or job acknowledgment, and result retrieval MUST perform a single lookup rather than waiting internally.
- **FR-006**: Separate synchronous and asynchronous higher-level helpers MUST compose public command operations to submit once and return an aggregated, validated outcome for one or more explicit device identifiers. Helpers MUST preserve the supplied client's ownership and context and MUST NOT close it or mutate caller-provided command data.
- **FR-007**: Helpers MUST accept immediate results and deferred jobs. Deferred jobs MUST retain a valid job identifier and aggregate results until every requested device has responded. Completion MUST depend on device presence, including empty output, rather than output truthiness. Immediate incomplete outcomes without a job identifier MUST fail with partial-result context.
- **FR-008**: Helpers MUST expose independent, configurable command-execution and overall wait limits plus a polling interval. The default overall wait limit MUST be 300 seconds and the default interval 10 seconds. The wait budget MUST account for elapsed submission, retrieval, and intervening waits; no new retrieval or wait may start after the deadline, and each network-operation timeout MUST be capped by the remaining budget when a request starts. Existing synchronous transport timeouts bound individual network operations rather than total request duration, so a request already in progress MAY finish after the wait deadline. Such a late response MUST retain known partial-result context but MUST NOT produce whole-operation success after the deadline. Asynchronous waiting MUST also enforce a cancellable overall deadline. Polling MUST be reserved for contract-defined pending results and missing device responses, not arbitrary errors.
- **FR-009**: A helper timeout or ordinary failure MUST identify its stage, requested devices, known job identifier, completed responses, missing devices, and underlying cause where applicable. It MUST distinguish validation, submission, retrieval, contract, incomplete-result, and timeout failures. Submitted commands MUST NOT be automatically resubmitted or remotely cancelled after failure or a local deadline.
- **FR-010**: Asynchronous client operations and the asynchronous helper MUST allow other asynchronous work to proceed during network operations and polling waits. Cancellation MUST stop further local work, preserve cancellation semantics, and expose known job and partial-result context. Cancellation MUST NOT become an ordinary successful or failed command response.
- **FR-011**: Helpers MUST reject invalid targets, blank commands, invalid option values, and detached background commands before any submission. The individual submission operation MUST retain support for detached launch acknowledgments without claiming process completion.
- **FR-012**: Aggregated responses MUST preserve exact reported output and associate it with the requested device identifier. They MUST retain reported platform result fields without inventing exit codes or output streams. Repeated responses MUST NOT discard previous results; unexpected device identifiers or malformed job/result responses MUST raise a contract failure.
- **FR-013**: Label, configuration, VPN, Parameter-application, and migration operations MUST preserve reference targeting and failure behavior. Both clients MUST expose a public device VPN operation that enables or disables VPN for one explicitly identified device. It MUST accept a validated VPN-specific payload, support optional advertisement of project-configured subnets when enabling with a default of disabled, and change no unrelated settings. The internal general-purpose daemon-change operation MUST NOT be exposed as a public client method. Client methods MUST NOT perform key lookup, availability prechecks, fleet selection, readiness polling, deployment deletion, or post-migration VPN setup implicitly.
- **FR-014**: Public documentation MUST include runnable synchronous and asynchronous examples for discovery and inspection, registration/onboarding authorization, individual command submission/retrieval, device VPN enable/disable and route advertisement, and the response-waiting helper. Helper examples MUST cover single-device and multi-device use, immediate and deferred execution, empty output, timeout/partial results, and asynchronous cancellation, and state that stopping local waiting does not stop remote execution.
- **FR-015**: Acceptance MUST compare both client modes and both helpers against network-isolated reference fixtures for requests, success responses, pending/partial results, and failures. Evidence MUST include every operation in FR-001, all command edge cases, VPN enable/disable with default and explicit route advertisement, and consistency checks comparing corresponding client names, arguments, defaults, result models, context overrides, and shared error categories; unavailable live credentials MUST NOT substitute for compatibility verification. Acceptance MUST also verify that the feature adds no public deprecated topic operations, agent-upgrade methods, or generic daemon-change methods. Existing daemon, file-upload, Parameter storage, and other resource workflows MUST retain their public behavior.

### Key Entities *(include if feature involves data)*

- **Device**: Project-scoped identity with name, lifecycle state, description, runtime configuration, labels, configuration variables, reported system details, and available health/failure information. Summary and detail views may expose different fields.
- **Device Registration and Onboarding Authorization**: Requested initial settings, resulting identity, and platform-issued token and script command used by the operator to onboard hardware.
- **Device Label / Configuration Variable**: Device-associated key/value record with its own identity for update and deletion.
- **Device Selection**: Platform-supported expression for choosing device records without implicit fleet-wide execution.
- **Device VPN State / Parameter Application**: Explicit device targets and VPN enabled/disabled state with optional route advertisement, or selected Parameter trees, with platform-reported acknowledgment or individual successes and errors.
- **Command Request**: Device targets, exact text, execution context, execution timeout, and immediate/deferred/background choices.
- **Command Job and Device Response**: Deferred execution identity and reported result for an individual device; missing output and an empty output string have different meanings.
- **Command Workflow Outcome**: Requested devices, optional job identity, collected responses, unresolved devices, and failure/cancellation context when the workflow does not complete.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can complete discovery, registration, onboarding-authorization retrieval, inspection, update, and deletion in both usage modes with 100% of explicitly submitted request values preserved in transmitted payloads according to the documented operation contract and 100% of returned device identifiers preserved exactly. This measures request/response fidelity; it does not promise persistence of server-ignored fields or device readiness after an acknowledgment.
- **SC-002**: Every operation listed in FR-001 has equivalent user-visible outcomes in both usage modes for its documented success and failure scenarios, with zero hidden follow-up management operations and 100% of corresponding public names, arguments, defaults, result contracts, and shared failure categories consistent across usage modes.
- **SC-003**: One helper invocation collects exact responses from at least three explicitly selected devices responding in separate batches, with 100% of responses retained, empty output counted correctly, and zero duplicate command submissions.
- **SC-004**: Every injected pending, incomplete-result, malformed-response, authorization, transport, timeout, and cancellation scenario produces the specified inspectable outcome; zero unresolved devices are reported as having responded.
- **SC-005**: Deadline tests MUST show zero new retrievals or waits starting after the configured deadline, every started request's network-operation timeout no greater than its remaining wait budget, and zero successful outcomes from responses arriving after that deadline. A synchronous request already in progress may finish later according to the transport's timeout semantics. Asynchronous waiting ends within the configured overall limit plus one second of scheduling tolerance; in asynchronous wait/cancellation tests, a separate task scheduled every 50 milliseconds continues to run with no gap above 250 milliseconds under controlled conditions.
- **SC-006**: An operator following each documented command-helper example completes the workflow or identifies the failed stage and missing devices without consulting reference internals or writing custom waiting/aggregation logic.

## Assumptions

- This invocation creates the specification; implementation design, public method/model names, and executable tasks follow in planning.
- Device Management means the individual operations listed in FR-001, inferred from rio CLI and SDK v1 and narrowed by the explicit scope clarifications in this session. Deprecated topic operations and agent upgrade are excluded; only VPN control is exposed for device daemon changes. The references use the legacy Device Management service even when callers use SDK v2 for other resources; this feature does not assume equivalent v2 device lifecycle or command operations exist.
- Users already have credentials and required permissions in the source project and, for migration, the destination project. The existing Device Management service and onboarded agents are external dependencies; local compatibility fixtures do not require a live device.
- Existing file-upload, shared-URL, daemon-read, and deployment operations supply those already-supported capabilities. Duplicate legacy log/file-upload wrappers, deprecated topic list/status/subscribe/unsubscribe operations, deprecated system-metric subscription operations, deprecated agent-upgrade requests, telemetry queries, HWIL provisioning, installer execution, SSH/SCP, generic daemon-change interfaces, fleet-wide or post-migration VPN orchestration, regex/name-based fleet helpers, automatic readiness waits, automatic retries/resume, output streaming, and remote command cancellation are outside scope.
- Reference-compatible command defaults are immediate execution, detached background disabled, and a 300-second execution timeout. Individual command contracts permit omitted shell/user values to retain platform defaults; helper defaults use the CLI's `root` user and `/bin/bash` shell when unspecified. Environment variables default to empty and working directory is omitted unless supplied. The helper does not reproduce the CLI's additional command-text wrapping.
- Existing SDK v2 resource and Parameter methods establish public client conventions; the v1 SDK and rio CLI establish service operation semantics. Where v1 method shapes differ, new Device methods follow SDK v2 conventions without inventing request fields or response contents. Internal routing choices for VPN belong in planning.
- Request serialization and server persistence are separate acceptance concerns. Historical registration fields ignored by the service and empty/null description updates treated as no-ops remain governed by the documented service contract; returned data must not invent their persistence.
- Low-level methods preserve platform payload contracts rather than mutable v1 resource objects, legacy aliases, local output printing, or v1 orchestration. Architecture selection is explicit rather than a hidden second operation inside listing. Acceptance/rejection is a device update, not an additional workflow.
- Reference quirks such as retrying every non-success retrieval response or returning after the first responding device do not establish helper completion rules. The explicit error, aggregation, and deadline requirements above govern the new helper.
- Constitution 1.0.0 governs planning and implementation: equivalent one-operation clients, typed validated payloads in model modules, separate helper modules composing public operations, documented contracts, and repository quality checks. FR-001 and the entity list identify affected operation/model contracts; internal design belongs in the plan.
- Reference documentation: [rio CLI Device commands](https://cli.rapyuta.io/device.html) and [SDK v1 Device module](https://sdk.rapyuta.io/device.html). Local source evidence inspected: `/home/ankit/Projects/Work/rapyuta-io-cli` revision `27bb77bb912705b58a5de0a2e99848dc023ba322` (`riocli/device/execute.py`, `config.py`, `create.py`, `onboard.py`, `model.py`, `vpn.py`, and migration in `util.py`) and `/home/ankit/Projects/Work/rapyuta-io-sdk` revision `739a6fe44600ff0964fa56b04878ddb21e76b5be` (`rapyuta_io/clients/device_manager.py`, `device.py`, `model.py`, route constants, `rapyuta_io/rio_client.py` VPN feature submission, and device command fixtures/tests). Inspected source files had no pending modifications. Actual operation payloads take precedence over inconsistent reference prose; planning must record fixture provenance and any contract gaps.
