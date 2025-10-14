# ruff: noqa
from rapyuta_io_sdk_v2.async_client import AsyncClient
from rapyuta_io_sdk_v2.client import Client
from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.utils import walk_pages

# Import all models directly into the main namespace
from .models import (
    # Core models
    Secret,
    StaticRoute,
    Disk,
    Deployment,
    Package,
    Project,
    Network,
    User,
    Organization,
    # List models
    ProjectList,
    DeploymentList,
    DiskList,
    NetworkList,
    PackageList,
    SecretList,
    StaticRouteList,
    # Managed service models
    ManagedServiceProvider,
    ManagedServiceBinding,
    ManagedServiceBindingList,
    ManagedServiceInstance,
    ManagedServiceInstanceList,
    ManagedServiceProviderList,
)

__version__ = "0.3.0"
