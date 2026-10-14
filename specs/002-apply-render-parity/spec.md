# Feature Specification: Apply Template Rendering Parity

**Feature Branch**: `feat/apply`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "Implement Parity in the Apply implementation of CLI and SDK. Support the custom rio Filter functions with same signature. Support ansible filters. Build Test suite with examples from rapyuta-charts: postgis, gateway, gostproxy. Use different values to generate the output from CLI first, then use them as fixtures and compare SDK generated output against it."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Render manifests with rio filters (Priority: P1)

An SDK user prepares a manifest that already works with `rio apply`. Its custom filter expressions produce the same manifest values through the SDK, without rewriting the chart.

**Why this priority**: Existing charts depend on the rio filter names and argument order. A different calling convention prevents reuse.

**Independent Test**: Prepare small manifests containing each custom filter with positional and named arguments. Compare the rendered values with controlled CLI results, including a device with multiple candidate interfaces.

**Acceptance Scenarios**:

1. **Given** `{{ 'fallback' | getenv('RIO_TEST_VALUE') }}` and an environment variable set to `chosen`, **When** the CLI and SDK prepare the manifest, **Then** both render `chosen`.
2. **Given** the same expression with the variable unset, **When** the CLI and SDK prepare the manifest, **Then** both render `fallback`.
3. **Given** `{{ device_name | get_intf_ip(interface='eth0,tailscale0') }}` and controlled device information where `eth0` has no address and `tailscale0` has two, **When** the CLI and SDK prepare the manifest, **Then** both render the first `tailscale0` address.
4. **Given** no candidate interface with an address, **When** either renderer evaluates `get_intf_ip`, **Then** preparation fails with the device name and requested interface list identified.

---

### User Story 2 - Reuse Ansible filter expressions (Priority: P1)

An SDK user renders an existing Apply manifest containing Ansible filters and receives the same values as the CLI for the same inputs.

**Why this priority**: Manifests that depend on Ansible filters cannot be adopted in the SDK until those filters are available with compatible behavior.

**Independent Test**: Render representative expressions from each CLI supported Ansible filter group and compare results with the CLI. Include an undefined value using Jinja's built in `default` behavior.

**Acceptance Scenarios**:

1. **Given** a manifest using filters from the CLI's core, URL, URL split, math, and encryption groups, **When** it is prepared through either path with equivalent inputs, **Then** filter names, arguments, and rendered values agree.
2. **Given** an undefined value followed by `default('fallback')`, **When** the manifest is rendered, **Then** it resolves to `fallback` under both paths.
3. **Given** an unknown filter or an invalid filter argument, **When** preparation runs, **Then** the SDK identifies the source manifest and filter error before any resource operation starts.

---

### User Story 3 - Detect parity regressions with chart fixtures (Priority: P1)

A maintainer can run repeatable tests using real postgis, gateway, and gostproxy chart examples. Expected manifests are captured from the CLI first, so SDK changes are checked against an independent reference.

**Why this priority**: Small filter tests cannot detect how filters interact with chart values, conditionals, nested data, and resource manifests.

**Independent Test**: For each chart, capture CLI rendered manifests for at least two distinct value sets, then prepare the same templates and inputs through the SDK and compare every selected output document with its checked in fixture.

**Acceptance Scenarios**:

1. **Given** selected postgis chart templates and two distinct value sets, **When** the CLI outputs have been captured as fixtures and the SDK renders the same cases, **Then** every resulting manifest document matches its CLI counterpart in content and scalar types.
2. **Given** selected gateway chart templates and two distinct value sets, **When** the same process runs, **Then** every resulting manifest document matches its CLI counterpart, including branches selected by the changed values.
3. **Given** selected gostproxy chart templates and two distinct value sets, **When** the same process runs, **Then** every resulting manifest document matches its CLI counterpart; the suite exercises both the supplied VPN address path and the `get_intf_ip` path with controlled device information.
4. **Given** a maintainer needs to refresh fixtures, **When** they follow the documented capture procedure, **Then** they can identify the CLI revision, chart revision, selected templates, input values, environment settings, device information, and output for each case without access to a live platform account.

### Edge Cases

- `getenv` accepts the piped default as its first argument and the environment variable name as its second; an empty but present environment value stays empty.
- `get_intf_ip` accepts the piped device name first and the comma separated interface list second, including the `interface=` keyword form used by gostproxy. It checks interfaces in the supplied order and chooses the first available address on the first matching interface.
- Device lookup or readiness failures must remain visible as preparation errors; the renderer must not silently substitute an empty address.
- A manifest that does not use `get_intf_ip` can still be prepared offline without device lookup or platform access.
- Ansible filters must not replace the established behavior of Jinja's built in `default` filter.
- Filter failures must identify the input file and must not trigger apply or delete operations.
- Fixture comparisons may ignore YAML formatting and mapping key order; they must preserve document count and order, keys, values, list order, and scalar types.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The SDK Apply manifest preparation workflow MUST recognize the CLI's custom filter names `getenv` and `get_intf_ip` in both synchronous and asynchronous use. Their template signatures and observable results MUST match the CLI: `getenv(default, env_var)` and `get_intf_ip(device_name, interface)`.
- **FR-002**: `getenv` MUST return the named environment variable's value when present, including an empty string, and otherwise return the piped default.
- **FR-003**: `get_intf_ip` MUST resolve the piped device name in the intended project, inspect the comma separated interface candidates in order, and return the first address on the first candidate with an address. It MUST provide an actionable failure if lookup, readiness, or address selection fails. The SDK caller MUST be able to supply the needed resolution context without relying on CLI configuration.
- **FR-004**: The SDK Apply renderer MUST support the filter names and calling behavior that the CLI exposes from Ansible's core, URL, URL split, math, and encryption filter groups. It MUST retain Jinja's built in `default` behavior where the CLI does.
- **FR-005**: A supported SDK installation MUST make the Ansible filters available during manifest preparation. If filter support is unavailable or a filter call fails, the SDK MUST report a source attributed preparation error rather than silently rendering a different result.
- **FR-006**: Both sync and async SDK Apply entry points MUST resolve the same manifest content for equal files, values, secrets, explicit rio context, environment, and controlled device information. Preparing manifests that do not need device information MUST remain offline capable.
- **FR-007**: The regression suite MUST use real selected templates from `rapyuta-charts` postgis, gateway, and gostproxy. It MUST include at least two different value sets per chart, with each set changing one or more resulting manifest fields or selected branches.
- **FR-008**: For every selected chart case, expected output MUST be generated by the CLI before the corresponding SDK expectation is evaluated and stored as a checked in fixture. The fixture record MUST identify the CLI revision, chart revision, source templates, value inputs, relevant environment, controlled device information, and capture procedure.
- **FR-009**: The suite MUST compare the SDK's resulting manifests with those CLI generated fixtures as structured documents. It MAY normalize insignificant formatting and mapping order, but MUST detect missing or extra documents, changed values or types, and changed sequence order.
- **FR-010**: The suite MUST include direct success and failure cases for both rio filters, representative Ansible filters from every CLI supported group, and the `default` collision behavior. Fixture tests MUST run without platform mutations or reliance on a live account.
- **FR-011**: The feature MUST preserve the existing Apply resource preparation, validation, and execution contract apart from the additional rendering capabilities. Filter resolution failures MUST stop preparation before resource operations begin.

### Key Entities

- **Manifest template**: A chart or standalone Apply file containing value expressions and resource documents.
- **Render context**: Ordered values and secrets, explicit rio context, relevant environment values, and any device information needed by a filter.
- **Reference fixture**: A CLI generated set of resolved manifest documents plus enough provenance to reproduce it.
- **Parity case**: One selected template set, render context, and reference fixture against which SDK output is compared.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All selected postgis, gateway, and gostproxy cases pass structured parity comparison for at least two distinct value sets per chart, with zero unexplained document, value, or type differences.
- **SC-002**: All direct tests for both rio filters and at least one representative filter from each of the five CLI supported Ansible groups pass against CLI reference behavior.
- **SC-003**: At least one gostproxy case exercises interface address lookup and one exercises an explicitly supplied VPN address, both without a live platform account during regression testing.
- **SC-004**: A maintainer can reproduce every reference fixture from its recorded inputs and revisions; repeating capture under the recorded conditions yields the same structured documents.
- **SC-005**: Every tested invalid filter call fails during preparation with an identifiable source and before any platform mutation.

## Assumptions

- This feature extends the existing SDK Applier described in `specs/001-sdk-applier/spec.md`; it does not change resource lifecycle rules or add new resource kinds.
- The checked in fixtures are generated from the CLI implementation, not synthesized from SDK output. The CLI and chart revisions used for capture are pinned in fixture metadata so future behavior changes can be reviewed deliberately.
- `get_intf_ip` needs project and device resolution information. The SDK supplies this through caller provided context while keeping its manifest syntax unchanged; the exact public interface is a planning decision.
- Chart parity is measured on selected manifest templates and documented value sets from each named chart. Unrelated chart packaging, image builds, and live deployment behavior are outside this feature.
- Structured manifest equality is the relevant output contract; whitespace and YAML key formatting are presentation details.
