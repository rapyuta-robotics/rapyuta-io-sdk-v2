<p align="center">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="./assets/v2sdk-logo-dark.png">
      <img alt="rapyuta.io SDK v2" src="./assets/v2sdk-logo-light.png">
    </picture>
</p>

# rapyuta.io SDK v2

Typed synchronous and asynchronous clients for rapyuta.io, with optional declarative workflows. Requires Python 3.13 or newer.

## Installation

```bash
pip install rapyuta-io-sdk-v2
# Optional dependencies:
pip install 'rapyuta-io-sdk-v2[configtree,apply,charts]'
# YAML files in Parameter directory uploads:
pip install 'rapyuta-io-sdk-v2[parameters]'
```

Installing an extra supplies dependencies. Enable the corresponding runtime feature in `Configuration.features` before using it. Core API access and pagination need no feature flags.

The `parameters` extra supplies YAML parsing for Parameter uploads and needs no feature flag. JSON and binary Parameter transfers work with the core installation.

## Configuration

`Configuration` is a Pydantic `BaseSettings` class. Values come from constructor arguments, `RIO_` environment variables, the rio-cli JSON configuration, then defaults, in that order. Nested settings use `__`, for example `RIO_FEATURES__APPLY=true`.

The SDK automatically reads rio-cli's platform-specific `config.json`. Select another file with `config_file=` or `RIO_CONFIG`; an explicitly selected file must exist and contain a JSON object. The implicit default file is optional. The reader recognizes CLI keys including `project_id`, `organization_id`, `email_id`, and `v2api_host`, and ignores unrelated CLI settings. It never writes the file or logs in automatically.

```python
from rapyuta_io_sdk_v2 import Client, Configuration

config = Configuration(config_file="/path/to/config.json")
# Applications that supply all settings can disable CLI file loading:
config = Configuration(
    load_cli_config=False,
    auth_token="TOKEN",
    organization_guid="ORGANIZATION_GUID",
    project_guid="PROJECT_GUID",
    environment="ga",
)

with Client(config) as client:
    projects = client.list_projects()  # One API request, typed page response.
```

Optional `v2_api_host`, `core_api_host`, and `rip_host` override environment defaults. Their corresponding `resolved_*` properties expose the effective URLs. Parameter and Device Management calls use `core_api_host`, which defaults to the v1 API server for the selected environment. Set `RIO_CORE_API_HOST` or the rio-cli `core_api_host` setting for a custom server; local mode also accepts `LOCAL_CORE_API_HOST`.

## Typed API calls and request context

Python fields use snake_case; explicit Pydantic aliases preserve API spelling, including acronyms. Models accept both Python field names and API payload names. Call `model_dump(by_alias=True, mode="json")` for the wire representation. User dictionary keys, such as labels, remain unchanged.

Client methods accept model instances. Convert raw dictionaries explicitly with `Project.model_validate(data)`. Structured responses are models, including opaque `RootModel` envelopes for endpoints without a stable schema. Raw ConfigTree key reads return text; decode that text in your application if needed.

```python
from rapyuta_io_sdk_v2 import Project, RequestContext

project = Project(metadata={"name": "example"}, spec={})
with Client(config) as client:
    created = client.create_project(project)
    client.update_project(created, project_guid=created.metadata.guid)
    page = client.list_projects(
        context=RequestContext(organization_guid="ANOTHER_ORGANIZATION")
    )
```

`RequestContext` overrides scope for one call. It also accepts scope switches (`with_project`, `with_organization`, `with_group`), `request_id`, `x_checksum`, `content_type`, and additional `headers`. Additional headers take precedence over generated headers. Path identifiers remain explicit method arguments.

Both clients support injected HTTPX clients through `transport=`. Closing an SDK client closes a transport it created; the caller remains responsible for an injected transport.

## Pagination

Direct list calls fetch one page. A reusable paginator can collect all items or stream items and pages, preserving filters and context:

```python
with Client(config) as client:
    paginator = client.paginate(client.list_projects, limit=100)
    projects = paginator.all()  # Flat list[Project], no manual extend loop.
    for project in paginator.items():
        print(project.metadata.name)
    for page in paginator.pages():
        print(page.metadata.continue_)
```

Each traversal starts afresh. Requests are lazy, and early termination avoids fetching further pages. Missing continuation tokens, empty pages, and short pages end traversal; repeated nonterminal cursors raise `PaginationError`.

```python
from rapyuta_io_sdk_v2 import AsyncClient


async def projects_async(config):
    async with AsyncClient(config) as client:
        return await client.paginate(client.list_projects).all()
```

Authentication calls on `AsyncClient` are awaited as well.

## Parameter directory workflows

Upload and download v1 Parameter trees from directories. Uploads default to `as_folder=True`: the root directories are tree names, nested directories become folders, and files can appear at any depth. Set `as_folder=False` to use v1's alternating attribute/value directory layout.

```python
with Client(config) as client:
    client.upload_configurations("./parameters", tree_names=["robot"])
    client.apply_parameters(["DEVICE_UUID"], tree_names=["robot"])
    client.download_configurations("./downloaded", tree_names=["robot"])
```

Both transfers accept `delete_existing_trees=True` to replace selected trees at the destination. JSON and YAML files within the API size limit are stored as text file nodes. Other files and oversized payloads use signed blob uploads. No Parameter label API is exposed. The same methods on `AsyncClient` are awaited.

These filesystem methods delegate to workflows in `parameter_operations`; neither client inherits from a Parameter mixin. Each transfer may make several API calls to process its files and trees.

## Device Management

Device Management uses typed models for device provisioning, commands, configuration variables, and labels. Listing returns `list[Device]`; the v1 endpoint does not use v2 continuation pagination.

```python
from rapyuta_io_sdk_v2 import (
    DeviceCommand, DeviceCreate, DeviceLabelCreate, wait_for_command_result,
)

with Client(config) as client:
    devices = client.list_devices(online=True)
    onboarding = client.create_device(
        DeviceCreate(name="robot", python_version="3", config_variables={"runtime_docker": True})
    )
    client.create_device_label("DEVICE_UUID", DeviceLabelCreate(key="fleet", value="warehouse"))
    command = client.execute_command(
        ["DEVICE_UUID"], DeviceCommand(cmd="uname -a", run_async=True)
    )
    # One request, returning immediately even if the result is pending.
    result = client.get_command_result(command.jid, ["DEVICE_UUID"])
    if result.is_pending:
        # Optional polling, with timing chosen by the caller.
        result = wait_for_command_result(
            client, command.jid, ["DEVICE_UUID"], retry_interval=2, timeout=300
        )
```

Each Device client method makes one API request. `get_command_result` exposes `is_pending` and `http_status_code`, preserving the service payload. The separate `wait_for_command_result` and `async_wait_for_command_result` utilities poll the corresponding client method until results are available or their timeout expires. They forward `RequestContext` and propagate API errors. The timeout bounds polling; configure HTTP request timeouts on the transport separately. The async utility uses awaited requests and sleeps, and supports cancellation.

```python
from rapyuta_io_sdk_v2 import AsyncClient, async_wait_for_command_result

async with AsyncClient(config) as client:
    result = await async_wait_for_command_result(
        client, "COMMAND_JOB_ID", ["DEVICE_UUID"], retry_interval=2, timeout=300
    )
```

Architecture selection uses the separate `select_devices` method. To combine it with listing filters, intersect the returned device IDs explicitly:

```python
from rapyuta_io_sdk_v2 import DeviceSelectionQuery

with Client(config) as client:
    selected = client.select_devices(DeviceSelectionQuery(
        operator="$or",
        specs={"operator": "$or", "args": [
            {"operator": "$eq", "args": ["cpuarch", "x86_64"]},
            {"operator": "$eq", "args": ["cpuarch", "amd64"]},
        ]},
    ))
    selected_ids = {device.uuid for device in selected}
    devices = [device for device in client.list_devices(online=True) if device.uuid in selected_ids]
```

Device configuration variable and label methods provide list/create/update/delete operations; device deletion, daemon patching, and Parameter application are also supported. All methods support `RequestContext`, and `AsyncClient` has the same API with awaited requests.

## ConfigTree settings source

Enable `features.configtree_source` to use the optional Pydantic Settings source:

```python
from pydantic_settings import BaseSettings
from rapyuta_io_sdk_v2.pydantic_source import ConfigTreeSource

source_config = Configuration(features={"configtree_source": True})


class ServiceSettings(BaseSettings):
    port: int

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            ConfigTreeSource(
                settings_cls, source_config, tree_name="default", key_prefix="service"
            ),
        )
```

The source loads when invoked, decodes base64 values and JSON, and nests slash-separated paths. It supports settings aliases, injected clients, and local JSON/YAML via `local_file=`. Local data is wrapped under the file stem: use `key_prefix="service"` with `service.yaml`. Pass `local_export=True` to unwrap CLI export records containing `value` and `metadata`; ordinary local files preserve those application fields. Owned clients close after loading; injected clients stay open.

## Resource operations

Resource models inherit from `ResourceModel`, which provides `apply()`, `delete()`, `apply_async()`, and `delete_async()`. Enable `features.apply` to invoke these methods. Already validated resources need only the core SDK dependencies.

```python
from rapyuta_io_sdk_v2 import Role

operation_config = Configuration(features={"apply": True})
role = Role(metadata={"name": "reader"}, spec={})
with Client(operation_config) as client:
    result = role.apply(client)
    deletion = role.delete(client)


async def apply_role(config):
    async with AsyncClient(config) as client:
        return await role.apply_async(client)
```

Apply and delete operations return a `ResourceResult` containing the outcome, response resource, and error details. Clients are explicit arguments and remain owned by the caller. Operations use a copy of the input model, preserving its data. Models call their typed client methods directly; shared apply/delete policy handles conflicts, readiness, retained resources, and failures.

Supported models also expose `create()` and `create_async()`, and mutable models expose `update()` and `update_async()`. These methods invoke typed client methods and return typed responses; resource-specific lookups stay on the model. The Apply feature flag controls the higher-level apply/delete orchestration.

## Apply

Enable `features.apply` and install `[apply]` to render manifests and coordinate multiple resource operations:

```python
from rapyuta_io_sdk_v2.apply import Applier

apply_config = Configuration(features={"apply": True})
with Client(apply_config) as client:
    applier = Applier(client, resources="manifests/", values=["values.yaml"])
    plan = applier.plan()  # Validate and order without API calls.
    preview = applier.apply(dry_run=True)  # Planned outcomes without API calls.
    report = applier.apply()
    report.raise_for_errors()  # Retains the partial report on failure.
```

Inputs can be typed resources, mappings, YAML/JSON files, directories, or globs. Templates use Jinja with strict undefined variables; values merge in order. Pass decrypted values with `secrets=` and custom Jinja filters with `filters=`.

Supported kinds: Organization, Project, Package, Deployment, Disk, Network, StaticRoute, Secret, UserGroup, Role, RoleBinding, and ServiceAccount. Package identity includes its version. Apply orders dependencies first; deletion reverses that order and respects `rapyuta.io/deletionPolicy=retain`. Dependencies outside the submitted manifests refer to existing resources. Deployment dependencies marked `wait` receive readiness checks.

Execution uses at most six workers by default. Failure stops new work after the current batch settles, and the report includes failed and skipped resources. After rendering and validation, `Applier` invokes the resource models' operations. Custom resources subclass `ResourceModel`, declare a fixed `resource_kind`, implement their client calls, and register through `resource_models={"MyKind": MyResource}`. Models provide their own identity, dependencies, reference aliases, and operation-specific input schemas. SOPS execution, Ansible filters, and declarative v1 Device operations remain outside the apply engine.

`AsyncApplier` provides awaited `apply()` and `delete()`; local `render()` and `plan()` remain synchronous.

## Charts

Charts require both `features.apply` and `features.charts`, plus `[charts]`:

```python
from rapyuta_io_sdk_v2.charts import ChartRepository

chart_config = Configuration(features={"apply": True, "charts": True})
with Client(chart_config) as client, ChartRepository(chart_config) as repository:
    with repository.find("my-chart", version="1.0.0") as chart:
        report = chart.apply(client, values=["overrides.yaml"])
        report.raise_for_errors()
```

Repositories support a custom index URL or a branch preview. An omitted version selects the first published index entry. Relative archive URLs resolve against the index URL. Downloads and extraction have size limits; unsafe archive paths, links, and special files are rejected. Context managers clean up downloaded charts and owned transports.

Charts use the same rendering, planning, Apply, and deletion engine. Packaged values load before caller overrides. `AsyncChartRepository` and `AsyncChart` provide async equivalents.

## Development

```bash
uv sync --all-extras --dev
uv run pytest tests/ --cov
ruff check .
ruff format --check .
uv build
```

Tests use mocked transports and require no live platform credentials. See [CONTRIBUTING.md](CONTRIBUTING.md).
