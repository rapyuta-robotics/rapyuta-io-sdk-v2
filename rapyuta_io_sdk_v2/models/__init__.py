# Copyright 2026 Rapyuta Robotics
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Models package for Rapyuta IO SDK v2.

This module provides flattened imports for all model classes.
"""

# Deployment models
from rapyuta_io_sdk_v2.models.daemons import (
    Daemon,
)
from rapyuta_io_sdk_v2.models.deployment import (
    Deployment,
    DeploymentList,
)
from rapyuta_io_sdk_v2.models.disk import (
    Disk,
    DiskList,
)
from rapyuta_io_sdk_v2.models.fileupload import (
    FileUpload,
    FileUploadList,
    FileUploadSpec,
    FileUploadStatus,
    SharedURL,
    SharedURLList,
    SharedURLSpec,
)
from rapyuta_io_sdk_v2.models.managedservice import (
    ManagedServiceBinding,
    ManagedServiceBindingList,
    ManagedServiceInstance,
    ManagedServiceInstanceList,
    ManagedServiceProvider,
    ManagedServiceProviderList,
)
from rapyuta_io_sdk_v2.models.network import (
    Network,
    NetworkList,
)
from rapyuta_io_sdk_v2.models.oauth2 import (
    OAuth2UpdateURI,
)
from rapyuta_io_sdk_v2.models.organization import (
    Organization,
)
from rapyuta_io_sdk_v2.models.package import (
    Package,
    PackageList,
)
from rapyuta_io_sdk_v2.models.project import (
    Project,
    ProjectList,
)
from rapyuta_io_sdk_v2.models.role import (
    Role,
    RoleList,
)
from rapyuta_io_sdk_v2.models.rolebinding import (
    BulkRoleBindingUpdate,
    RoleBinding,
    RoleBindingList,
)
from rapyuta_io_sdk_v2.models.secret import (
    Secret,
    SecretCreate,
    SecretList,
)
from rapyuta_io_sdk_v2.models.serviceaccount import (
    ServiceAccount,
    ServiceAccountList,
    ServiceAccountToken,
    ServiceAccountTokenInfo,
    ServiceAccountTokenList,
)
from rapyuta_io_sdk_v2.models.sshkey import (
    SSHKeySignRequest,
    SSHKeySignResponse,
)
from rapyuta_io_sdk_v2.models.staticroute import (
    StaticRoute,
    StaticRouteList,
)
from rapyuta_io_sdk_v2.models.user import (
    User,
    UserList,
    UserPermissions,
)
from rapyuta_io_sdk_v2.models.usergroup import (
    UserGroup,
    UserGroupCreate,
    UserGroupList,
)

# Disk models

# FileUpload models

# Managed Service models

# Network models

# OAuth2 models

# Organization models

# Package models

# Project models

# Role models

# Role Binding models

# Secret models

# SSH Key models

# Static Route models

# User models

# User Group models


__all__ = [
    "BulkRoleBindingUpdate",
    "Daemon",
    "Deployment",
    "DeploymentList",
    "Disk",
    "DiskList",
    "FileUpload",
    "FileUploadList",
    "FileUploadSpec",
    "FileUploadStatus",
    "ManagedServiceBinding",
    "ManagedServiceBindingList",
    "ManagedServiceInstance",
    "ManagedServiceInstanceList",
    "ManagedServiceProvider",
    "ManagedServiceProviderList",
    "Network",
    "NetworkList",
    "OAuth2UpdateURI",
    "Organization",
    "Package",
    "PackageList",
    "Project",
    "ProjectList",
    "Role",
    "RoleBinding",
    "RoleBindingList",
    "RoleList",
    "SSHKeySignRequest",
    "SSHKeySignResponse",
    "Secret",
    "SecretCreate",
    "SecretList",
    "ServiceAccount",
    "ServiceAccountList",
    "ServiceAccountToken",
    "ServiceAccountTokenInfo",
    "ServiceAccountTokenList",
    "SharedURL",
    "SharedURLList",
    "SharedURLSpec",
    "StaticRoute",
    "StaticRouteList",
    "User",
    "UserGroup",
    "UserGroupCreate",
    "UserGroupList",
    "UserList",
    "UserPermissions",
]
