# Research: Apply Template Rendering Parity

## Decision 1: Reuse the current preparation stage

**Decision**: Register filters in the existing `_loader.py` rendering environment and use the shared `prepare_source` path for both `Applier` and `AsyncApplier`. Keep `ImmutableSandboxedEnvironment` and `StrictUndefined`.

**Rationale**: Both public facades prepare manifests in their constructor before a client is supplied (`rapyuta_io_sdk_v2/apply/applier.py`). Existing loader errors already carry the source and `template` category. Baseline chart render probes completed offline: postgis produced 2 documents, gateway 2, and gostproxy 3; branch-changing values produced 4 documents for each chart. Jinja documents that `ImmutableSandboxedEnvironment` restricts mutation of built in mutable objects ([Jinja sandbox documentation](https://jinja.palletsprojects.com/en/stable/sandbox/)).

**Alternatives considered**: Replacing the SDK environment with the CLI's plain Jinja environment would weaken the SDK's established behavior. Deferring preparation until apply would break existing offline inspection and constructor validation.

## Decision 2: Preserve rio filter syntax with an explicit device resolver

**Decision**: Implement `getenv(default, env_var)` and `get_intf_ip(device_name, interface)` under their CLI names. Add a caller supplied synchronous `resolve_device_interfaces(project_guid, device_name) -> Mapping[str, Sequence[str]]` contract to `ManifestSource`. Pass the explicit project scope into preparation. Invoke the resolver only if `get_intf_ip` appears; select the first address from the first nonempty candidate interface in the input order.

**Rationale**: The CLI's functions and selection order are in `../rapyuta-io-cli/riocli/apply/filters.py`. Its device helper creates a CLI client, resolves the device, polls readiness, and refreshes. SDK v2 has no corresponding device listing/get operation, and SDK parsing happens before the apply/delete client argument. The resolver lets callers obtain ready device information with their own mechanism and lets tests provide a deterministic snapshot while leaving template signatures unchanged. A missing project scope or resolver fails only when the filter is invoked.

**Alternatives considered**: Copying CLI configuration/device code would couple the SDK to CLI state. Adding device API methods and moving async preparation into apply would enlarge the public API and change the existing lifecycle. A mapping-only input would cover fixtures but not callers that need to perform their own lookup/readiness step.

## Decision 3: Ship the CLI's Ansible groups as runtime support

**Decision**: Add `ansible-core>=2.21,<2.22` as a runtime dependency and register the CLI's `core`, `urls`, `urlsplit`, `mathstuff`, and `encryption` filter maps in that order. Skip the core map's `default` entry so Jinja's filter remains active. If import or initialization fails, surface an actionable error when preparing manifests; do not continue with a partial registry.

**Rationale**: The CLI registers these five groups and deliberately skips Ansible's `default` (`../rapyuta-io-cli/riocli/apply/util.py`). Its lock selects 2.21.4 on Python 3.12+, while the present CLI environment has 2.21.1; capture must record the installed version and align it with the SDK test environment. Ansible 2.21.4 lists Python 3.13 support ([PyPI package metadata](https://pypi.org/project/ansible-core/2.21.4/)). The official Ansible filter guide confirms pipe input and positional/named parameter conventions ([Ansible filter documentation](https://docs.ansible.com/projects/ansible-core/stable-2.21/plugins/filter.html)).

**Alternatives considered**: Optional Ansible support with only a warning would violate the spec's supported-installation guarantee. Reimplementing each filter would diverge from CLI behavior and require a far larger compatibility surface. Loading arbitrary Ansible collections would exceed the CLI's current registry.

## Decision 4: Compare raw parsed documents, not serialized resource models

**Decision**: Add `RenderedDocument(source, data)` to the typed inspection result. Populate it from deep copies of each prepared resource's pre-model parsed `source_data` in input order. Compare this data to CLI parsed documents with type-sensitive recursive comparison; ignore only YAML whitespace and mapping key order.

**Rationale**: The CLI's `print_manifests()` emits parsed dictionaries with `yaml.safe_dump_all`, whereas SDK `inspect().resolved_manifests` returns Pydantic models that may add defaults, canonicalize fields, or serialize aliases differently. The SDK already retains original parsed document data internally. A public inspection field makes the output useful to callers and keeps parity tests on a stable interface.

**Alternatives considered**: Comparing YAML text would fail on harmless formatting differences. Comparing model dumps would confound rendering parity with model normalization. Reading private loader state in tests would create a brittle fixture contract.

## Decision 5: Keep CLI fixture capture independent and reproducible

**Decision**: Copy only tracked chart templates and safe sample/base values into test fixtures, then create two synthetic value sets per chart. Use the CLI's local Apply parser to capture expected parsed documents before SDK comparisons. Record the CLI commit, chart commit, actual Ansible/Jinja versions, template paths and hashes, values, synthetic rio context, environment variables, and mocked device interface data. Ordinary tests load checked in copies and never call the CLI, network, or platform.

**Rationale**: `rio chart apply` downloads a chart; the local Apply parser is the same rendering path without that dependency. The CLI parse code is in `../rapyuta-io-cli/riocli/apply/parse.py`. Chart baseline and branch probes showed all three template sets are locally renderable by the current SDK. Avoid the chart repo's untracked `gateway/values.testing.yaml` and other local-only files. For the gostproxy interface branch, patch the CLI's device information provider during explicit capture. Set `ANSIBLE_LOCAL_TEMP` to a writable temp path because current Ansible initialization otherwise tries to write under `~/.ansible/tmp` in restricted environments.

**Alternatives considered**: Deriving fixtures from SDK output would not provide an independent oracle. Depending on sibling checkouts during every test would make CI nonreproducible. Using live devices would make the suite slow and account dependent.

## Open questions

None block design. The exact synthetic values and source hashes will be finalized during fixture capture and recorded in provenance.
