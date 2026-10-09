# rapyuta.io SDK v2 Constitution

## Core Principles

### I. Modern Python SDK

The project MUST provide a Python SDK for the rapyuta.io Platform. Implementation
MUST support the Python versions declared in `pyproject.toml`, currently Python
3.13 and newer. Public interfaces MUST include type annotations and document their
inputs, outputs, and failure behavior. These requirements make the SDK usable as
a typed library in downstream Python applications.

### II. One-to-One API Clients

`Client` and `AsyncClient` MUST expose API call methods that each correspond to a
single rapyuta.io API operation. Each method MUST preserve that operation's
request and response semantics. Corresponding synchronous and asynchronous
methods MUST provide equivalent API coverage and model contracts; asynchronous
methods MUST use awaitable I/O. API call methods MUST NOT orchestrate multiple
platform operations or embed higher-level workflows. Shared transport concerns,
such as authentication and error handling, MUST preserve the public operation
contract. This keeps platform API behavior predictable across both clients.

### III. Pydantic Request and Response Contracts

Every API call method in `Client` and `AsyncClient` MUST use Pydantic classes to
represent its request and response payloads. Request payloads MUST be validated
and serialized through these models, and response payloads MUST be parsed and
validated into these models before being returned. Public payload contracts MUST
NOT rely on untyped dictionaries or raw transport responses. Scalar routing
arguments, such as resource identifiers, MAY remain scalar parameters; operations
without a request or response payload MUST document that absence. Model fields
MUST use Python `snake_case` names and explicit aliases where the platform's wire
keys differ. Typed contracts make validation and wire-format compatibility
explicit and consistent across both clients.

### IV. Separate Higher-Level Modules

Higher-level constructs and helpers MUST be defined in their own modules outside
the `Client` and `AsyncClient` implementation modules. Workflows that combine API
operations MUST compose the public client methods from those modules. Client
modules MUST remain focused on individual API operations and the transport
behavior needed to execute them. This separation allows convenience abstractions
to evolve without changing the clients' one-to-one API contracts.

### V. Ruff Compliance

Every change MUST satisfy Ruff linting and formatting requirements configured in
`pyproject.toml`. Both `ruff check .` and `ruff format --check .` MUST pass using
the repository's required Ruff version. Contributors MUST refactor code to meet
the configured limits rather than weaken rules or add blanket suppressions.
Necessary suppressions MUST identify the specific rule and document their reason,
consistent with `CONTRIBUTING.md`. Ruff version changes MUST update the
configuration, CI, and contributor commands together. A shared quality gate keeps
SDK code consistent and reviewable.

## Technology Constraints

- The package MUST retain its identity as `rapyuta-io-sdk-v2` with the Python
  import namespace `rapyuta_io_sdk_v2`.
- Request and response classes MUST live in the SDK's model modules and use
  Pydantic for runtime validation and serialization.
- API serialization MUST preserve platform field names and distinguish omitted
  fields from explicitly supplied values according to the operation's contract.
- The configured Python compatibility range and Ruff settings in
  `pyproject.toml` MUST govern implementation choices. Contributor instructions
  and CI checks MUST remain consistent with that configuration.

## Development and Review Workflow

Specifications and implementation plans MUST identify the affected API
operations, request and response models, synchronous and asynchronous methods,
and any separate helper modules. Reviews MUST check compliance with each core
principle and document any discovered violations.

Changes to API contracts or behavior MUST include appropriate verification of
request serialization, response validation, and corresponding client behavior.
Reviewers MUST verify that higher-level orchestration resides in separate
modules. Ruff lint and format checks MUST pass before changes are merged.

The current contributor commands are:

```bash
uvx ruff==0.16.9 check .
uvx ruff==0.16.9 format --check .
```

Existing code that conflicts with this constitution MUST be identified as
noncompliant during relevant reviews; its presence MUST NOT establish an
exception for new or modified code.

## Governance

This constitution governs project specifications, plans, implementation, and
reviews. Conflicts with other project guidance MUST be resolved in favor of this
constitution or through an explicit amendment.

Amendments MUST document the proposed rule changes, their rationale, their effect
on existing code and documentation, and any required migration work. Project
maintainers MUST approve amendments through the project's review process before
adoption. Each amendment MUST update the constitution version and last-amended
date while preserving the original ratification date.

Constitution versions MUST follow semantic versioning: a MAJOR increment for
backward-incompatible principle removals or redefinitions, a MINOR increment for
new principles or materially expanded guidance, and a PATCH increment for
clarifications or other non-semantic edits. Every specification, plan, and code
review MUST assess constitution compliance. Any proposed exception MUST be
resolved through an approved amendment rather than an undocumented waiver.

**Version**: 1.0.0 | **Ratified**: 2026-10-09 | **Last Amended**: 2026-10-09
