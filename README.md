# Rapyuta IO SDK v2

Rapyuta IO SDK v2 provides a comprehensive set of tools and functionalities to interact with the rapyuta.io platform.

## Installation

```bash
pip install rapyuta-io-sdk-v2
```

## Configuration

To use the SDK, you need to configure it with your Rapyuta IO credentials and environment settings.

### From a Configuration File

You can create a Configuration object from a JSON file:

```python
from rapyuta_io_sdk_v2.config import Configuration, Client

config = Configuration.from_file("/path/to/config.json")
client = Client(config)
```

### Using Email and Password

```python
from rapyuta_io_sdk_v2.config import Configuration, Client

config = Configuration(organization_guid="ORGANIZATION_GUID")
client = Client(config)
client.login(email="EMAIL", password="PASSWORD")
```

## Usage

You can call multiple methods for projects, packages, deployments, etc.

* To List Projects

```python
projects = client.list_projects()
print(projects)
```

* To List Deployments

```python
print(client.list_deployments())
```

## More Operations

The SDK supports many more operations such as managing disks, networks, secrets, and static routes. Refer to the source code for detailed method definitions and usage.

## Contributing

We welcome contributions! Please read our [contributing guidelines](CONTRIBUTING.md) to get started.