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

## Contributing

We welcome contributions. Please read our [contribution guidelines](CONTRIBUTING.md) to get started.
