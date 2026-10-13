# SDK Rendering Contract

This contract extends the existing `ManifestSource`, `Applier`, `AsyncApplier`, and `InspectionResult` interfaces. Names here are the proposed public API for implementation; the template syntax is fixed by the CLI.

## Source and scope

```python
from collections.abc import Mapping, Sequence
from typing import Protocol

class DeviceInterfaceResolver(Protocol):
    def __call__(
        self, project_guid: str, device_name: str
    ) -> Mapping[str, Sequence[str]]: ...

ManifestSource(
    *, files=(), resources=(), values=(), secrets=(), rio=None,
    interface_resolver: DeviceInterfaceResolver | None = None,
)

Applier(source, options=ApplierOptions(scope=ResourceScope(project_guid="...")))
AsyncApplier(source, options=ApplierOptions(scope=ResourceScope(project_guid="...")))
```

The resolver receives the project GUID before the device name. It returns interface names and ordered address lists for a ready device. The caller owns lookup, readiness, and any cache or I/O. A missing project GUID, missing resolver, failed lookup, or invalid result affects only manifests that evaluate `get_intf_ip` and raises a file attributed `ApplierValidationError` with `category="template"`. If `rio.project.guid` is supplied, it must match the explicit project scope for an interface lookup. The SDK does not create or close a client for rendering.

## Filter behavior

| Template form | Required behavior |
|---------------|-------------------|
| `{{ 'fallback' | getenv('VAR') }}` | Call equivalent of `getenv(default, env_var)`; return present environment value, even if empty; otherwise return `fallback`. |
| `{{ device | get_intf_ip('eth0,tailscale0') }}` | Call equivalent of `get_intf_ip(device_name, interface)` and choose first address from first available candidate interface in the given order. |
| `{{ device | get_intf_ip(interface='eth0,tailscale0') }}` | Same result using named `interface`. |
| `{{ missing | default('fallback') }}` | Keep Jinja's built in `default` semantics, including under `StrictUndefined`. |

The renderer registers Ansible's `core`, `urls`, `urlsplit`, `mathstuff`, and `encryption` filter maps in the CLI order. It skips Ansible core's `default`. Representative tests cover `combine` (core), `urldecode` (urls), `urlsplit` (urlsplit), `log` (mathstuff), and `vault`/`unvault` with a fixed salt and synthetic secret (encryption). Unknown filters, invalid calls, Ansible initialization failures, and resolver failures are source attributed preparation errors. No apply/delete operation starts after such a failure.

## Inspection output

```python
class RenderedDocument(SDKModel):
    source: SourceLocation
    data: dict[str, Any]


class InspectionResult(SDKModel):
    # existing fields remain
    rendered_documents: tuple[RenderedDocument, ...] = ()
```

For file inputs, `rendered_documents` contains deep copied parsed documents before model validation changes their shape. For caller supplied resource instances, it contains deep copied model representations. Document order matches source order, excluding empty YAML documents. `resolved_manifests` remains the validated resource model view. Both sync and async facades expose equivalent inspection content for equal inputs and resolver responses. Ordinary rendering and `inspect()` make no platform requests.

## Error examples

- Missing project scope: identify the manifest path and state that `get_intf_ip` requires `ApplierOptions.scope.project_guid`.
- Missing resolver: identify the manifest path and state that `ManifestSource.interface_resolver` is required.
- No candidate address: identify the manifest path, device name, and interface list.
- Unknown Ansible filter or bad argument: identify the manifest path and underlying filter failure without starting resource operations.

This contract changes no Client/AsyncClient API method, request model, response model, or resource lifecycle operation.
