<p align="center">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="./assets/v2sdk-logo-dark.png">
      <img alt="Telemetry Pipeline Logo" src="./assets/v2sdk-logo-light.png">
    </picture>
</p>

# rapyuta.io SDK v2

rapyuta.io SDK v2 provides a comprehensive set of tools and functionalities to interact with the rapyuta.io platform.

## Installation

Requires Python 3.13 or newer.

```bash
pip install rapyuta-io-sdk-v2
```

## Usage

To use the SDK, you need to configure it with your rapyuta.io credentials.

### From a Configuration File

You can create a `Configuration` object from a JSON file.

```python
from rapyuta_io_sdk_v2 import Configuration, Client

config = Configuration.from_file("/path/to/config.json")
client = Client(config)
```

### Using `email` and `password`

```python
from rapyuta_io_sdk_v2 import Configuration, Client

config = Configuration(organization_guid="ORGANIZATION_GUID")
client = Client(config)
client.login(email="EMAIL", password="PASSWORD")
```

You are now set to invoke various methods on the `client` object.

For example, this is how you can list projects.

```python
projects = client.list_projects()
print(projects)
```

### Typed API payloads

Model attributes use `snake_case`. Explicit aliases preserve the v2 API's JSON
keys when loading dictionaries or serializing with `by_alias=True`. Client
request bodies must be Pydantic models; convert existing manifests before
passing them to either `Client` or `AsyncClient`.

```python
from rapyuta_io_sdk_v2.models import Deployment

manifest = {
    "apiVersion": "api.rapyuta.io/v2",
    "kind": "Deployment",
    "metadata": {"name": "app", "projectGUID": "project-guid"},
    "spec": {"runtime": "cloud", "serviceAccount": "worker"},
}
body = Deployment.model_validate(manifest)
print(body.metadata.project_guid)
print(body.spec.service_account)
created = client.create_deployment(body)
print(created.metadata.guid)
wire_payload = body.model_dump(by_alias=True, exclude_unset=True, mode="json")
assert wire_payload == manifest
```

JSON responses, including OAuth2 clients, config trees, revisions, deployment
history and graphs, and file download URLs, are returned as Pydantic models.
Access their fields as attributes. Authentication helpers still return tokens,
and shared-URL redirects retain the HTTP response.

### Reusable resource applier

`Applier` and `AsyncApplier` prepare manifest files and typed resource instances
locally. Inspection and dry-run previews need no client and make no platform
requests. Live `apply` and `delete` calls receive the already configured client
as an argument; the caller owns its authentication, scope, transport settings,
and lifetime. A prepared facade can be reused sequentially with different
clients and scopes. An `Applier` cannot run inside an active event loop; use
`AsyncApplier` for native asynchronous execution. Its `workers` option bounds
active resource work, including readiness waits, and `readiness` controls
polling rounds and intervals.

The initial lifecycle coverage is Organization (update only; deletion is
unsupported), Project, Package, Deployment, Disk, Network, StaticRoute, Secret,
UserGroup, Role, RoleBinding, and ServiceAccount. Package versions remain
distinct. RoleBinding apply grants the typed role/subject/domain combination;
delete revokes that exact grant. Delete follows reverse dependency order,
honors `rapyuta.io/deletionPolicy: retain`, and treats an already absent resource
as a successful outcome. Dependencies order managed resources while external
references are resolved only during live work when needed.

```python
from rapyuta_io_sdk_v2 import Applier, Client, Configuration, ManifestSource

client = Client(Configuration.from_file("/path/to/config.json"))
applier = Applier(ManifestSource(files=("/path/to/manifest.yaml",)))
preview = applier.apply(dry_run=True)  # no client or platform access
result = applier.apply(client)  # the exact caller-owned client is used
```

Apply templates support the CLI's `getenv`, `get_intf_ip`, and five built in
Ansible filter groups. Ansible is installed with the SDK. For an interface
lookup, supply an explicit project scope and a caller owned resolver that
returns ready interface addresses. The resolver runs only when a template
evaluates `get_intf_ip`:

```python
from rapyuta_io_sdk_v2 import ApplierOptions, ResourceScope


def interfaces(project_guid: str, device_name: str) -> dict[str, list[str]]:
    return {"eth0": ["100.64.1.2"]}  # replace with your ready device snapshot


source = ManifestSource(
    files=("/path/to/manifest.yaml",),
    interface_resolver=interfaces,
)
options = ApplierOptions(scope=ResourceScope(project_guid="project-guid"))
documents = Applier(source, options).inspect().rendered_documents
print(documents[0].source, documents[0].data)
```

`rendered_documents` contains independent copies of the parsed manifests before
resource model normalization. See the [parity quickstart](specs/002-apply-render-parity/quickstart.md)
for fixture verification.

`ApplierExecutionError.result` contains the settled input-order outcomes after a
partial failure. Each outcome reports confirmed completed actions and whether a
write may have taken effect without a confirmed response. A definitive rejected
write is not counted as completed. Caller cancellation propagates as
`CancelledError`; inspect `last_result` after settlement. Direct resource calls
can expose the same progress by passing a fresh `MutationJournal` through
`ResourceContext`. The journal stores action/state metadata only, not payloads,
responses, exceptions, or clients.

Secret-file decryption is an explicit optional operation. Call
`decrypt_secret_file` or `async_decrypt_secret_file` yourself, then pass the
returned mapping through `ManifestSource.secrets`; loading and preview never
invoke SOPS automatically. Once supplied, decrypted mappings are ordinary input
data. See [offline preview](examples/applier/offline_preview.py), [sync apply](examples/applier/sync_apply.py), [async apply](examples/applier/async_apply.py), and [explicit secret decryption](examples/applier/encrypted_secrets.py).

For a single-resource workflow, each managed model also exposes paired
`apply`/`apply_async`, `create_object`/`create_object_async`,
`update_object`/`update_object_async`, and `delete_object`/`delete_object_async`
methods where those operations are supported. Pass the client and a
`ResourceContext` explicitly. To retain direct-call progress after a method
raises or is cancelled, provide a fresh journal:

```python
from rapyuta_io_sdk_v2.models import MutationJournal, ResourceContext

journal = MutationJournal()
context = ResourceContext(progress=journal)
try:
    role.apply(client, context=context)
except Exception:
    print(journal.snapshot())  # action/state metadata, without payloads
    raise
```

Async direct methods propagate the original `CancelledError`; inspect the
journal after cancellation settles to distinguish confirmed work from a write
whose effect is uncertain.

Commit information is now supplied through a revision model:

```python
from rapyuta_io_sdk_v2.models import ConfigTreeRevision, ConfigTreeRevisionMetadata

revision = ConfigTreeRevision(
    author="operator",
    message="Update configuration",
    metadata=ConfigTreeRevisionMetadata(labels={"release": "1"}),
)
client.commit_revision("settings", "revision-guid", revision)
```

Use `ConfigValues` for a map of `ConfigValue` entries, `ConfigKeyRename` for key
renames, and `ConfigKeyUpload` for raw string or bytes uploads. Decoded key
content is returned as `ConfigKeyContent`; its `.root` holds the decoded JSON/YAML
value (including dates and YAML binary values) or the original bytes for binary
downloads. Bulk role-binding updates return `BulkRoleBindingUpdate`. The retired
`update_project_owner` method has been removed.

## Contributing

We welcome contributions. Please read our [contribution guidelines](CONTRIBUTING.md) to get started.
