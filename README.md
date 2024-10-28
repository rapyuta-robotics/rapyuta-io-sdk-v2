# Rapyuta IO SDK v2
Rapyuta IO SDK v2 provides a comprehensive set of tools and functionalities to interact with the rapyut.io platform.

## Installation
```bash
pip install rapyuta-io-sdk-v2
```

### Quick Start
```python
from rapyuta_io_sdk_v2 import Configuration, Client

config = Configuration(email="user@email.com", 
                       password="password", 
                       organization_guid="organization_guid", 
                       project_guid="project_guid")

client = Client(config)
client.login()

# Get current project
project = client.get_project()
```

## Contributing

We welcome contributions! Please read our [contributing guidelines](CONTRIBUTING.md) to get started.