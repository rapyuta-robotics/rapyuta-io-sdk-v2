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

from rapyuta_io_sdk_v2.models.auth import (
    AuthSubject,
    AuthSubjectResponse,
    LoginRequest,
    TokenRequest,
    TokenResponse,
)
from rapyuta_io_sdk_v2.models.configtree import (
    ConfigKeyContent,
    ConfigKeyRename,
    ConfigKeyUpload,
    ConfigTree,
    ConfigTreeList,
    ConfigTreeRevision,
    ConfigTreeRevisionList,
    ConfigTreeRevisionMetadata,
    ConfigValue,
    ConfigValues,
)
from rapyuta_io_sdk_v2.models.daemons import (
    Daemon,
)
from rapyuta_io_sdk_v2.models.deployment import (
    Deployment,
    DeploymentGraph,
    DeploymentGraphEdge,
    DeploymentGraphNode,
    DeploymentHistory,
    DeploymentHistoryList,
    DeploymentList,
)
from rapyuta_io_sdk_v2.models.disk import (
    Disk,
    DiskList,
)
from rapyuta_io_sdk_v2.models.fileupload import (
    FileUpload,
    FileUploadDownloadResponse,
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
    OAuth2Client,
    OAuth2ClientList,
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
from rapyuta_io_sdk_v2.models.responses import (
    APIResponse,
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

__all__ = [
    "APIResponse",
    "AuthSubject",
    "AuthSubjectResponse",
    "BulkRoleBindingUpdate",
    "ConfigKeyContent",
    "ConfigKeyRename",
    "ConfigKeyUpload",
    "ConfigTree",
    "ConfigTreeList",
    "ConfigTreeRevision",
    "ConfigTreeRevisionList",
    "ConfigTreeRevisionMetadata",
    "ConfigValue",
    "ConfigValues",
    "Daemon",
    "Deployment",
    "DeploymentGraph",
    "DeploymentGraphEdge",
    "DeploymentGraphNode",
    "DeploymentHistory",
    "DeploymentHistoryList",
    "DeploymentList",
    "Disk",
    "DiskList",
    "FileUpload",
    "FileUploadDownloadResponse",
    "FileUploadList",
    "FileUploadSpec",
    "FileUploadStatus",
    "LoginRequest",
    "ManagedServiceBinding",
    "ManagedServiceBindingList",
    "ManagedServiceInstance",
    "ManagedServiceInstanceList",
    "ManagedServiceProvider",
    "ManagedServiceProviderList",
    "Network",
    "NetworkList",
    "OAuth2Client",
    "OAuth2ClientList",
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
    "TokenRequest",
    "TokenResponse",
    "User",
    "UserGroup",
    "UserGroupCreate",
    "UserGroupList",
    "UserList",
    "UserPermissions",
]
