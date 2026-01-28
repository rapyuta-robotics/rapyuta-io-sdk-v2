"""
Models package for Rapyuta IO SDK v2.

This module provides flattened imports for all model classes.
"""

# Deployment models
from rapyuta_io_sdk_v2.models.deployment import (
    Deployment as Deployment,
    DeploymentList as DeploymentList,
)

# Disk models
from rapyuta_io_sdk_v2.models.disk import (
    Disk as Disk,
    DiskList as DiskList,
)

# Managed Service models
from rapyuta_io_sdk_v2.models.managedservice import (
    ManagedServiceBinding as ManagedServiceBinding,
    ManagedServiceBindingList as ManagedServiceBindingList,
    ManagedServiceInstance as ManagedServiceInstance,
    ManagedServiceInstanceList as ManagedServiceInstanceList,
    ManagedServiceProvider as ManagedServiceProvider,
    ManagedServiceProviderList as ManagedServiceProviderList,
)

# Network models
from rapyuta_io_sdk_v2.models.network import (
    Network as Network,
    NetworkList as NetworkList,
)

# OAuth2 models
from rapyuta_io_sdk_v2.models.oauth2 import (
    OAuth2UpdateURI as OAuth2UpdateURI,
)

# Organization models
from rapyuta_io_sdk_v2.models.organization import (
    Organization as Organization,
)

# Package models
from rapyuta_io_sdk_v2.models.package import (
    Package as Package,
    PackageList as PackageList,
)

# Project models
from rapyuta_io_sdk_v2.models.project import (
    Project as Project,
    ProjectList as ProjectList,
)

# Role models
from rapyuta_io_sdk_v2.models.role import (
    Role as Role,
    RoleList as RoleList,
)

# Role Binding models
from rapyuta_io_sdk_v2.models.rolebinding import (
    RoleBinding as RoleBinding,
    RoleBindingList as RoleBindingList,
    BulkRoleBindingUpdate as BulkRoleBindingUpdate,
)

# Secret models
from rapyuta_io_sdk_v2.models.secret import (
    Secret as Secret,
    SecretList as SecretList,
    SecretCreate as SecretCreate,
)

# Static Route models
from rapyuta_io_sdk_v2.models.staticroute import (
    StaticRoute as StaticRoute,
    StaticRouteList as StaticRouteList,
)

# User models
from rapyuta_io_sdk_v2.models.user import (
    User as User,
    UserList as UserList,
)

# User Group models
from rapyuta_io_sdk_v2.models.usergroup import (
    UserGroup as UserGroup,
    UserGroupCreate as UserGroupCreate,
    UserGroupList as UserGroupList,
)

from rapyuta_io_sdk_v2.models.daemons import Daemon as Daemon

from rapyuta_io_sdk_v2.models.serviceaccount import (
    ServiceAccount as ServiceAccount,
    ServiceAccountList as ServiceAccountList,
    ServiceAccountTokenList as ServiceAccountTokenList,
    ServiceAccountToken as ServiceAccountToken,
    ServiceAccountTokenInfo as ServiceAccountTokenInfo,
)

# FileUpload models
from rapyuta_io_sdk_v2.models.fileupload import (
    FileUpload as FileUpload,
    FileUploadList as FileUploadList,
    FileUploadRequest as FileUploadRequest,
    FileUploadSpec as FileUploadSpec,
    FileUploadStatus as FileUploadStatus,
    SharedURL as SharedURL,
    SharedURLList as SharedURLList,
    SharedURLRequest as SharedURLRequest,
    SharedURLSpec as SharedURLSpec,
)
