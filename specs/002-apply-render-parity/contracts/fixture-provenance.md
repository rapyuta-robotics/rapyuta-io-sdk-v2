# CLI Fixture Provenance Contract

## Capture tool

The implementation will provide `scripts/capture_apply_parity.py` with these maintenance commands:

```text
<CLI Python> scripts/capture_apply_parity.py \
  --charts-root ../rapyuta-charts \
  --output tests/apply/fixtures/parity \
  --write

<CLI Python> scripts/capture_apply_parity.py \
  --charts-root ../rapyuta-charts \
  --output tests/apply/fixtures/parity \
  --verify
```

`--write` deliberately refreshes tracked source copies, inputs, expected output, expected failures, and provenance. `--verify` re-renders or replays each expected failure using the recorded environment and reports any drift without changing files. `--suite rio-filters`, `--suite ansible-filters`, and `--suite charts` select one fixture set; omitting `--suite` processes all three. Both modes must use the rio CLI's local Apply parser; neither contacts chart hosting or the platform. Ordinary SDK parity tests read committed fixtures and do not invoke the capture tool. Capture-tool unit tests use a stubbed CLI parser and temporary fixtures, so they also require no sibling checkout.

Set `ANSIBLE_LOCAL_TEMP` to a writable temporary directory for capture. Run the tool with the SDK environment's Python; it imports the parser from the sibling CLI checkout and supplements missing CLI dependencies from that checkout's environment. Capture records actual installed Python, Ansible, and Jinja versions, rather than assuming they match a lock file. Before rendering, `--verify` rejects any mismatch between those exact installed versions or the CLI revision and the recorded values; it leaves all fixture files unchanged. The capture tool rejects untracked chart source files. In `--verify` mode it also rejects source content that differs from the recorded chart revision; `--write` records any intentionally selected tracked revision.

Direct rio and Ansible filter references use checked in `rio-filters/cases.yaml` and `ansible-filters/cases.yaml` descriptors, respectively, with standalone copies in `manifests/`, CLI-rendered `outputs.yaml`, and `provenance.json` files beside each descriptor. The rio suite also has `rio-filters/errors.json`: for the no-address `get_intf_ip` case, it records the case ID, CLI exception type, and message with the absolute fixture directory replaced by a stable `manifests/` path. Each descriptor records its standalone manifest inputs and controlled environment or device responses. Run the matching `--suite` with `--write` before SDK assertions and with `--verify` to reproduce successful documents and expected failures. Verification requires the recorded failure type and message under the pinned CLI/runtime versions. The chart suite uses the per-chart `cases.yaml` inputs and the shared chart `provenance.json`.

## Required cases

| Chart/case | Inputs and branch | Expected baseline shape from research |
|------------|-------------------|---------------------------------------|
| `postgis/base` | Tracked `values.sample.yaml`, synthetic rio scope, all template YAML files | 2 documents |
| `postgis/standby` | Sample values with standby enabled and a changed database value | 4 documents |
| `gateway/base` | Tracked `values.yaml`, synthetic rio scope, all template YAML files | 2 documents |
| `gateway/toxiproxy` | Base values with toxiproxy enabled, synthetic version and one service | 4 documents |
| `gostproxy/direct-ip` | Tracked `values.yaml`, synthetic direct VPN IP, all template YAML files | 3 documents |
| `gostproxy/interface-ip` | VPN IP empty; candidate interfaces include one empty and one with two synthetic addresses; route suffix changed; CLI device helper stubbed | 4 documents |

The exact values and outputs belong in checked in fixture files. Synthetic values must not include production credentials. The interface-IP capture must exercise the CLI filter through its real template expression, with only the device information provider controlled.

## Provenance fields

Each fixture set records:

- CLI git commit and, for chart cases, chart git commit; assert every selected chart source is tracked and every source matches its recorded content hash.
- Actual Python, rio CLI, Ansible, and Jinja versions used to capture.
- Original chart-relative template paths or direct-filter manifest paths, copied source hashes, and input value hashes.
- Full synthetic value sets or paths to their checked in copies, effective value hashes, explicit rio context, and relevant environment variables.
- Controlled project/device/interface data for the interface case and the capture command.
- Ordered, parsed CLI output documents. Empty YAML documents are omitted.
- For expected CLI failures, the case ID, exception type, and message; the SDK no-address test checks the device name and requested interface list from this record while separately checking SDK source attribution.

Parity comparison loads those CLI documents and SDK `InspectionResult.rendered_documents[*].data` using the same safe YAML parser, then checks recursive equality with type-sensitive scalar comparison. Mapping key order and YAML formatting are ignored; document/list order is preserved. A mismatch must report chart, case, document index, and the first differing path.
