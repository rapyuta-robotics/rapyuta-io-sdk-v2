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

### Import and merge configuration trees

These helpers use an authenticated `Client` and existing trees. Project scope is
the default; pass `with_project=False` in the options for an organization tree.
The client must have the corresponding organization and project GUIDs configured.

```python
from pathlib import Path

from rapyuta_io_sdk_v2.configtree import (
    ImportOptions,
    import_configtree,
    merge_configtree,
)

revision_id = import_configtree(
    client,
    "settings",
    [Path("robot.json"), Path("site.yaml"), Path("fallback.yml")],
    options=ImportOptions(commit=True, update_head=True),
)
merged_id = merge_configtree(client, "settings", "org/shared/release")
```

Import accepts named UTF-8 JSON, YAML, and YML files with mapping roots. Each
filename stem prefixes its flattened keys. A child containing exactly `value`
and dictionary `metadata` supplies one value and an optional metadata attachment
at that same key. Import prepares every file before creating a revision. Its
`commit` and `update_head` choices are independent and both default to `False`.
The platform may reject selecting an uncommitted revision as head.

Merge accepts `org/<tree>` or `proj/<tree>`, optionally followed by a selector.
Selectors starting with `rev-` identify a revision; other selectors identify a
milestone. Without a selector, Merge reads the source head. It rejects shared
keys with different stored data or metadata before creating a destination
revision. A successful Merge creates one revision, commits it, and selects it as
head. Its parent is the destination head read at the start; concurrent head
changes are not retried or checked again before publication.

Use a revision context to edit its live pending key map. `store()` encodes a
logical value; direct edits to `keys` must remain valid `ConfigValue` payloads.
The context sends one batch on normal exit when the map is nonempty and can
optionally commit. Removing an entry from `keys` removes a pending write; it
does not delete a key inherited from the parent.

```python
from rapyuta_io_sdk_v2.configtree import Revision, RevisionOptions

with Revision(client, "settings", options=RevisionOptions(commit=True)) as revision:
    revision.store("robot/speed", 2, metadata={"unit": "m/s"})
    revision.store("robot/remove", True)
    del revision.keys["robot/remove"]
print(revision.revision_id)
```

The same operations are available with `AsyncClient` as
`import_configtree_async`, `merge_configtree_async`, and `AsyncRevision` using
`await` and `async with`. Their local `store()` method remains synchronous.
Invalid files, references, conflicting keys, and unsuccessful batch responses
raise `ConfigTreeInputError`, `ConfigTreeReferenceError`,
`ConfigTreeMergeConflictError`, and `ConfigTreeMutationError` respectively.
Transport and validation errors retain their original types. After creation,
failures and cancellation expose `configtree_revision_id` and
`configtree_stage` on the exception for manual recovery. The helpers do not
automatically roll back a revision that may have been created remotely.

### v1 Parameters and directory uploads

`Client` and `AsyncClient` expose typed v1 Parameter operations. Parameter calls
use `Configuration.core_api_host`, independently of the v2 API gateway. Production
and staging endpoints resolve from the environment. For local use, set
`core_api_host="http://localhost:8080"` or `LOCAL_COREAPI_HOST`; local v2 calls still
work when no core endpoint is configured. The override must be an HTTP(S) origin.
`Configuration.from_file()` also accepts the optional `core_api_host` key.

Each method performs one platform request and returns a named Pydantic response
whose `.data` contains the result. Async counterparts have the same arguments
and result models; await their calls.

| Method | Input | Response `.data` |
| --- | --- | --- |
| `list_parameter_trees` | Optional `ParameterTreeQuery(instances=("config.*",))` | Tree-name list |
| `create_parameter_tree` | Tree name; no body | Created name |
| `get_parameter_tree` | Tree name; no body | Recursive `ParameterNode` |
| `put_parameter_node` | Child path and `ParameterNodeWrite` | Written node |
| `delete_parameter_tree` | Tree name; no body | `"ok"` |
| `delete_parameter_node` | Child path and `ParameterNodeDelete` | `"ok"` |
| `list_parameter_blobs` | `ParameterBlobQuery(tree_names=("settings",))` | Completion flag and blob references |
| `prepare_parameter_upload` | Child path and `ParameterUploadMetadata` headers; no body | File node with reference and optional signed URL |
| `commit_parameter_upload` | Tree name and decimal reference string; no body | `ParameterCommitData(upload=True)` |

Tree names start with an alphanumeric character and contain up to 50 characters
from letters, digits, `.`, `_`, and `-`. Paths retain literal names; unsupported
backend names and traversal are rejected. Root creation fails if a root exists.
Child version `0` creates a new node. Use the version from a recursive tree read
for an existing child's update or deletion; the SDK does not refresh it silently.

```python
from rapyuta_io_sdk_v2 import ParameterNodeType, ParameterNodeWrite

client.create_parameter_tree("settings")
client.put_parameter_node(
    "settings/folder", ParameterNodeWrite(node_type=ParameterNodeType.FOLDER)
)
tree = client.get_parameter_tree("settings").data
print(tree.children[0].version)
```

The separate helpers submit directories using these public operations. Immediate
child directories become trees; loose root files, symbolic links and special
entries are reported as skipped. Defaults select every tree, create folder
nodes below the roots, and preserve existing remote trees by failing on a
conflicting root. Selection matches exact local directory names.

```python
from rapyuta_io_sdk_v2 import ParameterUploadOptions
from rapyuta_io_sdk_v2.exceptions import ParameterUploadError
from rapyuta_io_sdk_v2.helpers import upload_parameters

try:
    result = upload_parameters(
        client,
        "/path/to/source",
        options=ParameterUploadOptions(tree_names=("settings",)),
    )
    print(result.completed_trees)
except ParameterUploadError as error:
    print(error.failure.path, error.failure.stage)
    print(error.partial_result.completed_files)
```

Set `delete_existing_trees=True` to delete and recreate only selected trees.
Set `as_folder=False` for the legacy value/attribute hierarchy. Legacy mode
reports files under attribute directories as skipped and validates the
one-attribute-child restriction for value directories before making changes.
Legacy directory names cannot have extensions or repeat an attribute in a branch.

Small `.yaml` files must contain mappings; `.json` files must contain valid JSON.
Their original UTF-8 text, including line endings, stays inline if the reference
serialized-payload estimate plus 200 bytes fits 128 KiB. Invalid small candidates
fail before the stored-size decision. Files larger than 128 KiB and other
extensions use blobs without structured parsing. Blob transfers use bounded
4 MiB blocks and original-byte MD5 checksums, with a maximum file size of
209715200000 bytes. Oversized files fail preflight before remote mutation.

`upload_parameters_async` has the same options and immutable results. It awaits
network I/O and offloads local disk work. Cancellation raises
`ParameterUploadCancelled`, an `asyncio.CancelledError` subtype with `.failure`
and `.partial_result`; inspect these fields and re-raise cancellation. Ordinary
failures and cancellation can leave remote changes. Partial results identify
confirmed files, directories, deletions and skips; unfinished files are not
reported as complete. Helpers provide no automatic rollback or retry.

Helpers keep caller-supplied platform and storage clients open and close storage
clients they create. An injected storage client must have no auth, cookies or
custom headers and must disable redirects. Storage requests carry no platform
credentials. Duplicate content counts as complete only after its matching
reference, checksum and `Uploaded` status are verified.

Runnable [synchronous](examples/parameters/upload.py) and
[asyncio](examples/parameters/upload_async.py) examples use
`RAPYUTA_AUTH_TOKEN`, `RAPYUTA_PROJECT_GUID`, and optional
`RAPYUTA_ENVIRONMENT`/`RAPYUTA_CORE_API_HOST` environment variables:

```bash
uv run python examples/parameters/upload.py /path/to/source --tree settings
uv run python examples/parameters/upload_async.py /path/to/source --tree settings --inspect
```

Both accept `--recreate` and `--legacy`. See the
[validation quickstart](specs/001-parameter-uploads/quickstart.md) for the pinned
SDK v1 downloader round-trip and test commands. Existing v2 ConfigTree APIs and
`ConfigTreeSource` remain available with their existing contracts.

## Chart support

`Chart` and `AsyncChart` package existing Apply templates with metadata and
bundled values. They wrap the SDK Appliers and support local directories,
compressed tar archives, and published or branch-preview repositories.

```python
from rapyuta_io_sdk_v2 import Chart, ChartInputs, ChartSource

chart = Chart.load(
    ChartSource.from_directory("./my-chart"),
    inputs=ChartInputs(values={"name": "my-application"}),
)
print(chart.metadata.name, chart.metadata.version)
inspection = chart.inspect()
plan = chart.apply(dry_run=True)
# Execute with your configured, caller-owned SDK Client:
# result = chart.apply(client)
# result = chart.delete(client)
# result = chart.apply(client, delete_existing=True)
```

A chart directory contains `Chart.yaml`, `templates/`, and `values.yaml` when
bundled defaults are needed. Supported manifest files under `templates/` are
selected recursively in deterministic order, excluding hidden paths as in the CLI. No explicit values sources means
use `values.yaml`; any supplied mapping or ordered YAML/JSON source sequence
replaces those defaults. An explicit `{}` therefore does not load defaults.
Explicit sources merge using the existing Apply rules. Supply complete values,
secrets, and `rio` context through `ChartInputs`; encrypted secret files must be
decrypted explicitly with the existing secret-file helper first.

```python
from rapyuta_io_sdk_v2 import AsyncChart, ChartInputs, ChartSource

# Inside your application's async function:
chart = await AsyncChart.load(
    ChartSource.from_repository("gateway:1.0.0", branch="feature/my-chart"),
    inputs=ChartInputs(values="./complete-values.yaml", rio=rio_context),
)
inspection = chart.inspect()  # Already prepared; no I/O.
plan = await chart.apply(dry_run=True)
# result = await chart.apply(async_client)
```

The standard repository index and branch base are fixed constants. Branch URL
construction preserves `/` and encodes spaces and reserved characters just as
the rio CLI does. A non-empty branch overrides an explicit repository URL. An
unversioned chart selects the first repository entry and warns if several match;
an exact version selects its first matching entry. Only the first advertised
package URL is used. Catalog helpers expose metadata without terminal parsing:

```python
from rapyuta_io_sdk_v2 import ChartRepository

repository = ChartRepository(branch="feature/my-chart")
entries = repository.find_chart("gateway")
all_entries = repository.list_charts()
```

`AsyncChartRepository` provides awaitable `fetch_index`, `find_chart`, and
`list_charts`. Repository requests use a separate HTTPX transport; callers can
supply `http_client=` for private repositories, custom timeout policy, or mocks.
The SDK closes only acquisition clients it creates. Platform clients are supplied
only to live operations and remain open, unchanged, and caller-owned.

Loading validates metadata and confines extraction to an owned temporary root.
Extracted files are removed before loading returns. Prepared charts remain
usable after their source files disappear; load again to pick up changed inputs.
Local preparation and previews need no platform account. Remote loading contacts
only the selected repository/package source. Device-interface filters require
an explicit resolver; asynchronous preparation invokes that synchronous resolver
on a worker thread, so provide thread-safe resolution or prefetched data.

Recreation runs delete before apply under one operation guard. It returns the
final `ApplierResult`, while `chart.phase_results` retains both settled phases,
including partial failures or cancellation. A failed deletion never starts apply.
`chart.last_result` follows the existing Applier semantics; rejected preflight
publishes no new result. Existing Apply errors propagate unchanged, supplemented
with chart origin notes where needed. Acquisition errors expose
`ChartLoadError.stage`, `.category`, `.source`, and optional `.selector`.
Async cancellation settles active preparation and owned cleanup before returning;
it can wait for a caller-supplied resolver to finish. No rollback is claimed.

Standalone sync/async usage, explicit encrypted-secret inputs, and offline
preview commands are demonstrated in [sync_chart.py](examples/chart/sync_chart.py)
and [async_chart.py](examples/chart/async_chart.py). Run the focused regression
suite with `uv run pytest tests/chart -q`. The [Chart validation guide](specs/003-chart-support/quickstart.md)
describes CLI fixture replay and the six postgis/gateway/gostproxy parity cases.

## Contributing

We welcome contributions. Please read our [contribution guidelines](CONTRIBUTING.md) to get started.

## Device Management

`Client` and `AsyncClient` provide the same typed methods for the legacy Device
Management service, using `Configuration.core_api_host` and existing authentication
and context overrides. Each method makes one request. Await the corresponding
method on `AsyncClient`.

| Operations | Methods |
| --- | --- |
| Discovery and selection | `list_devices`, `select_devices`, `get_device` |
| Registration and onboarding authorization | `create_device`, `get_device_onboarding` |
| Device details/state and deletion | `update_device`, `delete_device` |
| Labels | `list_device_labels`, `create_device_labels`, `update_device_label`, `delete_device_label` |
| Configuration variables | `list_device_config_variables`, `create_device_config_variable`, `update_device_config_variable`, `delete_device_config_variable` |
| VPN | `set_device_vpn` |
| Parameter application | `apply_device_parameters` |
| Commands | `execute_device_command`, `get_device_command_result` |
| Migration | `migrate_device` |

Responses retain `status` and `response.data`. Registration/onboarding data is a
private token string with sibling `device_id` and `script_command`; it is not a
Device detail record. Label/configuration records carry numeric IDs for subsequent
updates/deletion. Mutations returning empty data use `DeviceMutationResponse`.
Explicit null/empty description updates are transmitted, but the service treats
them as no-ops. Registration serialization does not promise persistence of fields
ignored by the server.

VPN changes accept `DeviceVPNUpdate(vpn=True)` or `DeviceVPNUpdate(vpn=False)` for
one device. Enable route advertisement with
`DeviceVPNUpdate(vpn=True, config={"vpn": {"advertise_routes": True}})`; advertisement
defaults to false and uses project-configured routes. The result contains the
actual DeviceDaemon acknowledgment, which does not establish connectivity
readiness. The public interface supports VPN settings only. Deprecated topics,
agent upgrade, and general daemon changes are excluded.

The command methods submit once or retrieve one snapshot. Command operational
defaults are timeout=300, bg=false, run_async=false and env={}; `bg=True` returns a
launch acknowledgment even if deferred execution was also requested. A lookup
returns `DeviceCommandPendingResponse` only for the exact pending HTTP400 marker;
other HTTP failures remain terminal SDK errors.

Use the separate helpers to execute and collect every explicit target's output:

```python
from rapyuta_io_sdk_v2 import DeviceCommand, DeviceCommandWaitOptions
from rapyuta_io_sdk_v2.helpers import execute_device_command

outcome = execute_device_command(
    client,
    DeviceCommand(device_ids=("device-a", "device-b"), cmd="printf ''", run_async=True),
    options=DeviceCommandWaitOptions(wait_timeout=30, poll_interval=1),
)
for result in outcome.responses:
    print(result.device_guid, repr(result.output))  # Empty output is received output.
```

For async usage, import `execute_device_command_async` from the same module and
await it with an `AsyncClient`. Both helpers default to a 300-second local wait,
10-second polling interval, `/bin/bash` and `root` when shell/user are omitted.
They preserve caller inputs, transport ownership and selected context. Execution
timeout and local wait timeout are independent. Background commands cannot be
used with the response-waiting helpers.

`DeviceCommandError` exposes immutable `.failure` stage/identities and
`.partial_result` outputs; available causes are chained. `DeviceCommandTimeout`
also inherits `TimeoutError`. Synchronous requests already in progress may finish
after the deadline; valid late outputs enrich the timeout snapshot and do not
produce success. Async waiting has a cancellable overall deadline.
`DeviceCommandCancelled` inherits `asyncio.CancelledError`, preserves the same
context and should be re-raised. Local timeout/cancellation does not stop remote
execution, resubmit commands or perform cleanup requests.

Runnable examples: [sync management](examples/devices/manage.py),
[async management](examples/devices/manage_async.py),
[sync commands](examples/devices/command.py), and
[async commands/cancellation](examples/devices/command_async.py).
Run them with `--help` using the same configured environment as the SDK. Management
requires explicit device or returned record IDs. Command examples accept repeated
`--device`, exact `--command`, `--mode immediate|deferred`, `--wait-timeout`,
`--poll-interval`, and optional `--direct`/`--jid`; the async example also supports
`--cancel-after`. See the [validation guide](specs/002-device-management/quickstart.md)
for isolated acceptance evidence and optional live setup.
