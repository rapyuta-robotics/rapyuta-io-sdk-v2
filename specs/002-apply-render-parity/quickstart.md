# Quickstart: Validate Apply Rendering Parity

This guide describes the checks to run after the feature is implemented. It uses checked in fixtures for ordinary tests and needs no platform account.

## Prerequisites

- Python 3.13+, the project's dependencies, and the test dependency group.
- The checked in `tests/apply/fixtures/parity/` inputs and CLI reference outputs.
- For fixture replay or refresh: sibling `rapyuta-io-cli` and `rapyuta-charts` checkouts at the revisions recorded in fixture provenance. Run the capture tool with the SDK environment's Python so the recorded Python, Ansible, and Jinja versions match exactly. The tool imports the parser from the sibling CLI checkout. Set `ANSIBLE_LOCAL_TEMP` to a writable directory.

## Run the parity checks

From the SDK repository root:

```bash
uv sync --group dev
export ANSIBLE_LOCAL_TEMP=/tmp/ansible-apply-parity
uv run pytest tests/apply/test_filters.py tests/apply/test_chart_parity.py tests/apply/test_capture_apply_parity.py -q
uv run pytest tests/apply -q
uvx ruff==0.16.9 check .
uvx ruff==0.16.9 format --check .
```

Expected result: all direct filter and six chart cases pass. Sync and async inspection produce equal parsed documents for the same inputs. An unknown filter or missing resolver fails during preparation with its manifest path; no platform request is made.

## Verify or refresh CLI fixtures

This is a separate maintenance action. The tool imports oracle code from the CLI checkout while running with the SDK's pinned Python and dependencies:

```bash
export ANSIBLE_LOCAL_TEMP=/tmp/ansible-apply-parity
.venv/bin/python scripts/capture_apply_parity.py \
  --charts-root ../rapyuta-charts \
  --output tests/apply/fixtures/parity \
  --verify
```

To refresh intentionally, substitute `--write`, review the changed source copies, values, provenance, and CLI outputs, then run the parity checks above. The capture interface and provenance fields are specified in [fixture-provenance.md](contracts/fixture-provenance.md). The SDK source and inspection contract is in [sdk-rendering.md](contracts/sdk-rendering.md).

With no `--suite` argument, verification or refresh covers the direct rio filter cases, direct Ansible filter cases, and all three charts. Use `--suite rio-filters`, `--suite ansible-filters`, or `--suite charts` to work on one fixture set. Verification rejects a Python, Ansible, or Jinja version mismatch or a CLI revision mismatch before rendering, and does not rewrite fixtures.

The fixture cases cover the tracked postgis, gateway, and gostproxy template sets. The direct-IP and interface-IP gostproxy cases select both branches of the chart's device-address expression. The interface case uses a controlled device response, so verification never queries a live device.
