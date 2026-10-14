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

## Contributing

We welcome contributions. Please read our [contribution guidelines](CONTRIBUTING.md) to get started.
