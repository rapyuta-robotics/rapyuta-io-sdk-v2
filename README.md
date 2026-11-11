<p align="center">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="./assets/v2sdk-logo-dark.png">
      <img alt="Telemetry Pipeline Logo" src="./assets/v2sdk-logo-light.png">
    </picture>
</p>

# rapyuta.io SDK v2

rapyuta.io SDK v2 provides a comprehensive set of tools and functionalities to interact with the rapyuta.io platform.

## Installation

```bash
pip install rapyuta-io-sdk-v2
```

## Usage

To use the SDK, you need to configure it with your rapyuta.io credentials.

### From a Configuration File

You can create a `Configuration` object from a JSON file.

```python
from rapyuta_io_sdk_v2.config import Configuration, Client

config = Configuration.from_file("/path/to/config.json")
client = Client(config)
```

### Using `email` and `password`

```python
from rapyuta_io_sdk_v2.config import Configuration, Client

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

## Contributing

We welcome contributions. Please read our [contribution guidelines](CONTRIBUTING.md) to get started.
### StaticRoute rate limits

StaticRoute HTTP/HTTPS limits are optional, per client IP and per Traefik instance:

```python
from rapyuta_io_sdk_v2 import StaticRoute, StaticRouteSpec, StaticRouteRateLimit

route = StaticRoute(
    metadata={"name": "limited-route"},
    spec=StaticRouteSpec(
        rate_limit=StaticRouteRateLimit(average=100, period="1m", burst=20),
    ),
)
client.create_staticroute(route)
```

`average` must be an integer from 1 to 1,000,000. `period` is an optional
positive Go duration string, validated by the backend; its server default is
`1s`. `burst` is an optional non-negative int64. The companion backend defaults
an omitted or zero burst to `average`. The SDK preserves omitted fields and
explicit nulls without injecting server defaults. Omit `rateLimit` or set
`rate_limit=None` to disable limiting when creating or updating a route.
Existing deployments need a restart or reapply to copy updated route settings.
