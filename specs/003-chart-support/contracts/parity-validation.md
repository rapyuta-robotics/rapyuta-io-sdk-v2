# Chart Parity and Validation Contract

## Independent Reference Evidence

Use the inspected CLI revision `27bb77bb912705b58a5de0a2e99848dc023ba322` and chart revision `94e456aea0dcdd7d4493aa57662cc0b8815df0ef`. Existing manifest expectations and their Python/Jinja/Ansible provenance remain in `tests/apply/fixtures/parity/`; do not rewrite them to make the wrappers pass.

Extend `scripts/capture_apply_parity.py` with an explicit `--suite chart-workflows` path and independent `tests/chart/fixtures/workflows/` inputs, expectations, and provenance. Existing suite arguments, default all-suite behavior for the original suites, `--write`, and `--verify` contracts remain unchanged; chart workflows are selected explicitly. Preserve existing environment/revision verification rules. The new suite does not require the chart checkout unless its case uses chart source files.

The capture tool imports oracle modules from the selected `--cli-root` checkout and rejects ambient imports from a different checkout. Record the CLI revision, Python/dependency versions involved, case descriptor hashes, relevant CLI source hashes, controlled index/package data, and capture command. Reject unverified revision/environment drift before replay. Verification reads and compares without overwriting fixtures; only explicit `--write` refreshes them.

Capture CLI outputs before evaluating SDK expectations. Controlled cases call the CLI's branch/index/lookup utilities and Chart apply/delete workflow with repository requests and temporary package input controlled. Use two capture layers: replace Apply/Delete callbacks with recording fakes to verify Chart argument forwarding; separately execute the real `riocli.apply.apply.callback` while replacing its underlying Applier lifecycle methods, configuration, presentation, and confirmation boundaries to observe recreation's delete-then-apply orchestration. A fake apply callback alone cannot prove recreation ordering because the orchestration lives inside that callback. Patch boundaries to prevent live network/platform actions while preserving the decision code being measured. Persist structured decisions, callback inputs, phase order, and warning behavior. Normalize temporary absolute prefixes to declared chart-relative paths, ordered values/secrets arguments to a canonical sequence, and timestamps to equivalent JSON forms; do not normalize version order, URL choice, branch characters, or phase order.

## Required Workflow Cases

| Group | Cases and expected evidence |
| --- | --- |
| Branch URL | Normal name, slash/space, query character, Unicode/symbols; exact CLI URL. Empty branch source selection follows default/override. |
| Index choice | Default constant, custom index, branch override, branch retrieval failure without standard fallback. |
| Entry selection | Unversioned first entry, non-fatal multiple-version diagnostic, exact first match, missing name/version, duplicate versions with first match. |
| Catalog metadata | All-version exact-name lookup, exact-version lookup, list stable name ordering, optional description/created/digest/extra metadata. |
| Package URL | Multiple advertised URLs select only first, unusable first URL fails without trying the second. |
| Value forwarding | No explicit sources use package values; explicit file sequence replaces defaults and preserves order. Empty mapping is a separate SDK input-extension test. |
| Lifecycle callback | Ordinary apply, ordinary delete, recreation delete then apply, deletion error prevents apply, dry-run previews both phases and forwards readiness/workers. |

SDK controlled workflow results must match recorded CLI decisions. Error cases compare meaningful failure boundary and lack of fallback/mutations rather than CLI-specific exception classes or terminal colors.

## Existing Six Manifest Cases

Stage complete chart directories in a test-owned temporary directory around the existing fixture inputs. Supply recorded real `Chart.yaml` metadata copied from the pinned chart source; record its provenance in new chart fixtures. Copy each case's base values into `values.yaml` for bundle/default tests without changing old fixture paths. Postgis currently uses `values.sample.yaml`, and none of the selected old fixture sets includes metadata.

| Chart/case | Expected selected resource documents |
| --- | --- |
| postgis/base | 2 |
| postgis/standby | 4 |
| gateway/base | 2 |
| gateway/toxiproxy | 4 |
| gostproxy/direct-ip | 3 |
| gostproxy/interface-ip | 4 |

Use the case's complete merged input values for explicit-replacement tests; do not supply only its overrides and accidentally layer bundled defaults. Pass recorded rio/project context and controlled interface resolver unchanged. Compare `.inspect().rendered_documents` with existing CLI expectations before model normalization. Equality may ignore mapping-key order and YAML presentation; it must preserve scalar/key types, document/list order, count, and values. Both Chart facades must pass all six cases and both local/archive workflows; controlled repository loading proves acquisition equivalence separately.

## Ownership, Failure, and Async Acceptance

- Assert zero platform requests during load, inspect, and preview, and zero acquisition requests for local load. Normal tests never import rio or require a live account.
- Verify input mappings, local sources, provided HTTPX clients, and platform client configuration remain unchanged and caller transports remain usable. Owned HTTPX sessions close on success/failure/cancellation.
- Check all unsafe archive member types, traversal/collision paths, local links, malformed metadata, duplicate resource identities, cycles, undefined values, and bad defaults. Each error identifies stage/source or preserves an existing source-attributed Apply error.
- Verify eager extraction cleanup on success and every failure and cancellation boundary. Loaded charts remain usable after source deletion; subsequent inspection and operations use prepared data.
- Demonstrate unrelated async task progress during delayed index/package responses and controlled blocked filesystem/render work. Cancel in each phase and again while settlement/transport closure is in progress; after return assert no active worker, no owned temp directory, and no further requests.
- Verify recreation holds one guard through both phases, exposes exact existing results, preserves confirmed/uncertain progress, and never enters apply after deletion failure/cancellation. A failed preflight after a previous successful call must not copy stale results into `phase_results`.
- Check sequential scope rebinding, repeated previews, retained/absent resources, independent inspection copies, original cancellation type, and supported empty rendered collections against existing Apply behavior.

## Completion Evidence

All 20 functional requirements are mapped in [plan.md](../plan.md). Success criteria SC-001–SC-004 cover resource/input and source equivalence; SC-005–SC-006 cover progress, settlement, cleanup, and failures; SC-007 covers examples; SC-008–SC-009 cover the CLI workflow oracle and branch URL cases. Run focused tests once during development, then the relevant existing regression suites and pinned Ruff checks after implementation. Do not label this design as executed test evidence.
