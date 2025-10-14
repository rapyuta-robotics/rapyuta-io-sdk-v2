# Deployment and DeploymentList mocks using pydantic models
import pytest


from rapyuta_io_sdk_v2.config import Configuration

# -------------------- PROJECT --------------------


@pytest.fixture
def mock_response_project():
    return {
        "kind": "Project",
        "metadata": {"name": "test-project", "guid": "mock_project_guid"},
        "spec": {
            "users": [{"userGUID": "mock_user_guid", "emailID": "test.user@example.com"}]
        },
    }


@pytest.fixture
def project_body():
    return {
        "apiVersion": "api.rapyuta.io/v2",
        "kind": "Project",
        "metadata": {
            "name": "test-project",
            "labels": {"purpose": "testing", "version": "1.0"},
        },
        "spec": {
            "users": [{"emailID": "tst.user@example.com", "role": "admin"}],
            "features": {"vpn": {"enabled": False}},
        },
    }


@pytest.fixture
def project_model_mock():
    return {
        "apiVersion": "api.rapyuta.io/v2",
        "kind": "Project",
        "metadata": {
            "guid": "mock_project_guid",
            "name": "test-project",
            "labels": {"purpose": "testing", "version": "1.0"},
        },
        "spec": {
            "users": [{"emailID": "test.user@example.com", "role": "admin"}],
            "features": {"vpn": {"enabled": False}},
        },
    }


@pytest.fixture
def projectlist_model_mock(project_model_mock):
    return {
        "metadata": {
            "continue": 1,
        },
        "items": [project_model_mock],
    }


# -------------------- PACKAGE --------------------


@pytest.fixture
def package_body():
    return {
        "apiVersion": "apiextensions.rapyuta.io/v1",
        "kind": "Package",
        "metadata": {
            "name": "test-package",
            "version": "v1.0.0",
            "description": "Test package for demo",
            "labels": {"app": "test"},
            "projectguid": "mock_project_guid",
        },
        "spec": {"runtime": "cloud", "cloud": {"enabled": True}},
    }


@pytest.fixture
def cloud_package_model_mock():
    return {
        "apiVersion": "apiextensions.rapyuta.io/v1",
        "kind": "Package",
        "metadata": {
            "name": "gostproxy",
            "guid": "pkg-aaaaaaaaaaaaaaaaaaaa",
            "projectGUID": "project-aaaaaaaaaaaaaaaaaaaa",
            "creatorGUID": "test-creator-guid",
            "labels": {"app": "gostproxy"},
            "createdAt": "2025-09-22T07:30:13Z",
            "updatedAt": "2025-09-22T07:30:13Z",
            "version": "v1.0.0",
            "description": "",
        },
        "spec": {
            "runtime": "cloud",
            "executables": [
                {
                    "name": "gostproxy",
                    "type": "docker",
                    "docker": {
                        "imagePullPolicy": "IfNotPresent",
                        "image": "gostproxy:v1.0.0",
                        "pullSecret": {"depends": {}},
                    },
                    "limits": {"cpu": 0.25, "memory": 128},
                }
            ],
            "environmentVars": [
                {
                    "name": "DEVICE_NAME",
                    "description": "Device Name in Tailscale",
                }
            ],
            "ros": {},
            "endpoints": [
                {
                    "name": "gateway",
                    "type": "external-https",
                    "port": 443,
                    "targetPort": 80,
                }
            ],
            "cloud": {"replicas": 1},
        },
    }


@pytest.fixture
def device_package_model_mock():
    return {
        "apiVersion": "apiextensions.rapyuta.io/v1",
        "kind": "Package",
        "metadata": {
            "name": "database",
            "guid": "pkg-bbbbbbbbbbbbbbbbbbbb",
            "projectGUID": "project-aaaaaaaaaaaaaaaaaaaa",
            "creatorGUID": "test-creator-guid",
            "labels": {"app": "database"},
            "createdAt": "2025-09-22T07:12:54Z",
            "updatedAt": "2025-09-22T07:12:54Z",
            "version": "v1.0.0",
            "description": (
                "Database package for deploying postgres and postgres_exporter"
            ),
        },
        "spec": {
            "runtime": "device",
            "executables": [
                {
                    "name": "postgres",
                    "type": "docker",
                    "docker": {
                        "imagePullPolicy": "IfNotPresent",
                        "image": "postgis:16-3.4",
                        "pullSecret": {
                            "depends": {"kind": "secret", "nameOrGUID": "mock-secret"}
                        },
                    },
                }
            ],
            "environmentVars": [
                {
                    "name": "POSTGRES_MULTIPLE_DATABASES",
                    "default": "test_table, test_table2",
                }
            ],
            "ros": {},
            "device": {"arch": "amd64", "restart": "always"},
        },
    }


@pytest.fixture
def packagelist_model_mock(cloud_package_model_mock, device_package_model_mock):
    return {
        "metadata": {
            "continue": 1,
        },
        "items": [cloud_package_model_mock, device_package_model_mock],
    }


# -------------------- DEPLOYMENT --------------------


@pytest.fixture
def deployment_body():
    # Updated to match device_deployment_model_mock keys and values, but only using keys present in deployment_body
    return {
        "apiVersion": "apiextensions.rapyuta.io/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "device_deployment_sample",
            "depends": {
                "kind": "package",
                "nameOrGUID": "device-package",
                "version": "2.0.0",
            },
            "labels": {"app": "deviceapp"},
        },
        "spec": {
            "runtime": "device",
            "device": {"depends": {"kind": "device", "nameOrGUID": "device-sample-001"}},
            "restart": "always",
            "envArgs": [
                {"name": "DEVICE_ENV", "value": "true"},
                {"name": "DEVICE_ID", "value": "dev-001"},
                {"name": "DEVICE_SECRET", "value": "secret"},
            ],
        },
    }


@pytest.fixture
def cloud_deployment_model_mock():
    return {
        "kind": "Deployment",
        "apiVersion": "api.rapyuta.io/v2",
        "metadata": {
            "name": "cloud_deployment_sample",
            "guid": "dep-cloud-001",
            "projectGUID": "project-sample-001",
            "organizationGUID": "org-sample-001",
            "creatorGUID": "user-sample-001",
            "createdAt": "2025-01-01T10:00:00Z",
            "updatedAt": "2025-01-01T11:00:00Z",
            "deletedAt": None,
            "organizationName": "Sample Org",
            "projectName": "Sample Project",
            "depends": {
                "kind": "package",
                "nameOrGUID": "cloud-package",
                "version": "1.0.0",
            },
            "generation": 1,
            "labels": {"app": "cloudapp"},
            "region": "us",
        },
        "spec": {
            "runtime": "cloud",
            "envArgs": [
                {"name": "CLOUD_ENV", "value": "true"},
                {"name": "API_KEY", "value": "cloudapikey"},
                {
                    "name": "CLOUD_ENDPOINT",
                    "value": "cloud.example.com",
                    "exposed": True,
                    "exposedName": "CLOUD_ENDPOINT",
                },
            ],
            "features": {"vpn": {"enabled": True}},
            "staticRoutes": [
                {
                    "name": "cloudroute",
                    "url": "cloudroute.example.com",
                    "depends": {"kind": "staticroute", "nameOrGUID": "cloudroute-sample"},
                }
            ],
        },
        "status": {
            "status": "Running",
            "phase": "Succeeded",
            "executables_status": {
                "cloud_exec": {
                    "name": "cloud_exec",
                    "status": "running",
                    "reason": "CloudRunning",
                }
            },
            "dependencies": {},
        },
    }


@pytest.fixture
def device_deployment_model_mock():
    return {
        "kind": "Deployment",
        "apiVersion": "api.rapyuta.io/v2",
        "metadata": {
            "name": "device_deployment_sample",
            "guid": "dep-device-001",
            "projectGUID": "project-sample-001",
            "organizationGUID": "org-sample-001",
            "creatorGUID": "user-sample-001",
            "createdAt": "2025-01-02T10:00:00Z",
            "updatedAt": "2025-01-02T11:00:00Z",
            "deletedAt": None,
            "organizationName": "Sample Org",
            "projectName": "Sample Project",
            "depends": {
                "kind": "package",
                "nameOrGUID": "device-package",
                "version": "2.0.0",
            },
            "generation": 1,
            "labels": {"app": "deviceapp"},
        },
        "spec": {
            "runtime": "device",
            "envArgs": [
                {"name": "DEVICE_ENV", "value": "true"},
                {"name": "DEVICE_ID", "value": "dev-001"},
                {"name": "DEVICE_SECRET", "value": "secret"},
            ],
            "volumes": [
                {
                    "execName": "device_exec",
                    "mountPath": "/mnt/data",
                    "subPath": "/mnt/data",
                    "depends": {},
                }
            ],
            "features": {},
            "device": {"depends": {"kind": "device", "nameOrGUID": "device-sample-001"}},
        },
        "status": {
            "status": "Running",
            "phase": "Succeeded",
            "executables_status": {
                "device_exec": {
                    "name": "device_exec",
                    "status": "running",
                    "reason": "DeviceRunning",
                }
            },
            "dependencies": {},
        },
    }


@pytest.fixture
def deploymentlist_model_mock(cloud_deployment_model_mock, device_deployment_model_mock):
    return {
        "metadata": {
            "continue": 123,
        },
        "items": [cloud_deployment_model_mock, device_deployment_model_mock],
    }


# -------------------- DISK --------------------


@pytest.fixture
def disk_body():
    return {
        "apiVersion": "apiextensions.rapyuta.io/v1",
        "kind": "Disk",
        "metadata": {
            "name": "test-disk",
            "labels": {"app": "test"},
        },
        "spec": {
            "runtime": "cloud",
            "capacity": "4",
        },
    }


@pytest.fixture
def disk_model_mock():
    return {
        "kind": "Disk",
        "apiVersion": "api.rapyuta.io/v2",
        "metadata": {
            "name": "mock_disk_1",
            "guid": "disk-mockdisk123456789101",
            "projectGUID": "project-aaaaaaaaaaaaaaaaaaaa",
            "organizationGUID": "org-mock-789",
            "creatorGUID": "mock-user-guid-000",
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T01:00:00Z",
            "deletedAt": None,
            "organizationName": "Mock Org",
            "projectName": "Mock Project",
            "generation": 1,
        },
        "spec": {
            "runtime": "cloud",
            "capacity": "4",
        },
        "status": {
            "status": "Available",
        },
    }


@pytest.fixture
def disklist_model_mock(disk_model_mock):
    return {
        "metadata": {
            "continue": 1,
        },
        "items": [disk_model_mock],
    }


# -------------------- SECRET --------------------


@pytest.fixture
def secret_body():
    return {
        "apiVersion": "apiextensions.rapyuta.io/v1",
        "kind": "Secret",
        "metadata": {
            "name": "test_secret",
            "labels": {"app": "test"},
        },
        "spec": {
            "type": "Docker",
            "docker": {
                "username": "test-user",
                "password": "test-password",
                "email": "test@email.com",
                "registry": "https://index.docker.io/v1/",
            },
        },
    }


@pytest.fixture
def secret_model_mock():
    return {
        "apiVersion": "api.rapyuta.io/v2",
        "kind": "Secret",
        "metadata": {
            "createdAt": "2025-01-01T00:00:00Z",
            "creatorGUID": "mock-user-guid-000",
            "deletedAt": None,
            "guid": "secret-aaaaaaaaaaaaaaaaaaaa",
            "labels": {"app": "test"},
            "name": "test_secret",
            "organizationCreatorGUID": "mock-user-guid-000",
            "organizationGUID": "org-mock-789",
            "organizationName": "Mock Org",
            "projectGUID": "project-aaaaaaaaaaaaaaaaaaaa",  # <-- valid project GUID
            "projectName": "Mock Project",
            "region": "jp",
            "shortGUID": "abcde",
            "updatedAt": "2025-01-01T01:00:00Z",
        },
        "spec": {
            "docker": {
                "email": "test@example.com",
                "password": "password",
                "registry": "docker.io",
                "username": "testuser",
            }
        },
    }


@pytest.fixture
def secretlist_model_mock(secret_model_mock):
    return {
        "metadata": {
            "continue": 1,
        },
        "items": [secret_model_mock],
    }


# -------------------- STATIC ROUTE --------------------


@pytest.fixture
def staticroute_body():
    return {
        "apiVersion": "apiextensions.rapyuta.io/v1",
        "kind": "StaticRoute",
        "metadata": {
            "name": "test-staticroute",
            "region": "jp",
            "labels": {"app": "test"},
        },
    }


@pytest.fixture
def staticroute_model_mock():
    return {
        "kind": "StaticRoute",
        "apiVersion": "api.rapyuta.io/v2",
        "metadata": {
            "createdAt": "2025-01-01T00:00:00Z",
            "creatorGUID": "mock-user-guid-000",
            "deletedAt": None,
            "guid": "staticroute-aaaaaaaaaaaaaaaaaaaa",
            "labels": {"app": "test"},
            "name": "test-staticroute",
            "organizationCreatorGUID": "mock-user-guid-000",
            "organizationGUID": "org-mock-789",
            "organizationName": "Mock Org",
            "projectGUID": "project-aaaaaaaaaaaaaaaaaaaa",
            "projectName": "Mock Project",
            "region": "jp",
            "shortGUID": "abcde",
            "updatedAt": "2025-01-01T01:00:00Z",
        },
        "spec": {"sourceIPRange": ["10.0.0.0/24"], "url": "https://example.com"},
        "status": {
            "deploymentID": "deployment-123",
            "packageID": "package-123",
            "status": "Available",
        },
    }


@pytest.fixture
def staticroutelist_model_mock(staticroute_model_mock):
    return {
        "metadata": {
            "continue": 1,
        },
        "items": [staticroute_model_mock],
    }


# -------------------- NETWORK --------------------


@pytest.fixture
def network_body():
    return {
        "apiVersion": "apiextensions.rapyuta.io/v1",
        "kind": "Network",
        "metadata": {
            "name": "test-network",
            "region": "jp",
            "labels": {"app": "test"},
        },
        "spec": {
            "rosDistro": "kinetic",
            "runtime": "cloud",
            "type": "routed",
        },
    }


@pytest.fixture
def network_model_mock():
    return {
        "apiVersion": "apiextensions.rapyuta.io/v1",
        "kind": "Network",
        "metadata": {
            "createdAt": "2025-09-22T07:00:00Z",
            "creatorGUID": "mock-user-guid-000",
            "deletedAt": None,
            "guid": "network-aaaaaaaaaaaaaaaaaaaa",
            "labels": {"app": "test"},
            "name": "test-network",
            "organizationCreatorGUID": "mock-user-guid-000",
            "organizationGUID": "org-mock-789",
            "organizationName": "Mock Org",
            "projectGUID": "project-aaaaaaaaaaaaaaaaaaaa",
            "projectName": "Mock Project",
            "region": "jp",
            "shortGUID": "abcde",
            "updatedAt": "2025-09-22T07:10:00Z",
        },
        "spec": {
            "architecture": "amd64",
            "depends": {"kind": "Device", "nameOrGUID": "device-aaaaaaaaaaaaaaaaaaaa"},
            "discoveryServer": {"serverID": 1, "serverPort": 11311},
            "networkInterface": "eth0",
            "rabbitMQCreds": {"defaultPassword": "guest", "defaultUser": "guest"},
            "resourceLimits": {"cpu": 0.05, "memory": 256},
            "restartPolicy": "always",
            "rosDistro": "kinetic",
            "runtime": "cloud",
            "type": "routed",
        },
        "status": {"errorCodes": [], "phase": "InProgress", "status": "Running"},
    }


@pytest.fixture
def networklist_model_mock(network_model_mock):
    return {
        "metadata": {
            "continue": 1,
        },
        "items": [network_model_mock],
    }


# -------------------- CONFIG TREE --------------------


@pytest.fixture
def configtree_body():
    return {
        "apiVersion": "apiextensions.rapyuta.io/v1",
        "kind": "ConfigTree",
        "metadata": {
            "name": "test-configtree",
            "labels": {"app": "test"},
        },
    }


# -------------------- USER --------------------


@pytest.fixture
def mock_response_user():
    return {
        "kind": "User",
        "metadata": {"name": "test user", "guid": "mock_user_guid"},
        "spec": {
            "emailID": "test.user@example.com",
            "firstName": "Test",
            "lastName": "User",
            "userGUID": "mock_user_guid",
            "role": "admin",
            "organizations": [
                {
                    "guid": "mock_org_guid",
                    "name": "mock-org",
                    "shortGUID": "org123",
                    "creator": "mock_user_guid",
                }
            ],
            "projects": [
                {
                    "guid": "mock_project_guid",
                    "name": "mock-project",
                    "organizationGUID": "mock_org_guid",
                    "creator": "mock_user_guid",
                }
            ],
            "userGroupsMembers": [
                {
                    "guid": "mock_group_guid",
                    "name": "mock-group",
                    "organizationGUID": "mock_org_guid",
                    "role": "member",
                }
            ],
            "userGroupAdmins": [
                {
                    "guid": "mock_admin_group_guid",
                    "name": "mock-admin-group",
                    "organizationGUID": "mock_org_guid",
                    "role": "admin",
                }
            ],
        },
    }


@pytest.fixture
def user_body():
    return {
        "emailID": "test.user@example.com",
        "firstName": "Test",
        "lastName": "User",
        "userGUID": "mock_user_guid",
        "role": "admin",
    }


# -------------------- ORGANIZATION --------------------


@pytest.fixture
def mock_response_organization():
    return {
        "metadata": {
            "name": "test-org",
            "guid": "mock_org_guid",
            "projectGUID": "project-aaaaaaaaaaaaaaaaaaaa",
            "organizationGUID": "org-mock-789",
            "creatorGUID": "mock-user-guid-000",
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T01:00:00Z",
            "deletedAt": None,
            "organizationName": "Mock Org",
            "projectName": "Mock Project",
        },
        "spec": {
            "users": [
                {
                    "guid": "mock_user1_guid",
                    "firstName": "John",
                    "lastName": "Doe",
                    "emailID": "test.user1@rapyuta-robotics.com",
                    "roleInOrganization": "viewer",
                },
                {
                    "guid": "mock_user2_guid",
                    "firstName": "Jane",
                    "lastName": "Smith",
                    "emailID": "test.user2@rapyuta-robotics.com",
                    "roleInOrganization": "admin",
                },
            ]
        },
    }


@pytest.fixture
def organization_body():
    return {
        "metadata": {
            "name": "test-org",
            "guid": "mock_org_guid",
        },
        "spec": {
            "users": [
                {
                    "guid": "mock_user1_guid",
                    "firstName": "John",
                    "lastName": "Doe",
                    "emailID": "test.user1@rapyuta-robotics.com",
                    "roleInOrganization": "viewer",
                },
                {
                    "guid": "mock_user2_guid",
                    "firstName": "Jane",
                    "lastName": "Smith",
                    "emailID": "test.user2@rapyuta-robotics.com",
                    "roleInOrganization": "admin",
                },
            ]
        },
    }


# -------------------- MANAGED SERVICE --------------------


@pytest.fixture
def managedservice_model_mock():
    return {
        "apiVersion": "api.rapyuta.io/v2",
        "kind": "ManagedServiceInstance",
        "metadata": {
            "guid": "mock_instance_guid",
            "name": "test-instance",
            "creatorGUID": "creator-guid",
            "projectGUID": "project-aaaaaaaaaaaaaaaaaaaa",
            "labels": {"env": "test"},
        },
        "spec": {
            "provider": "elasticsearch",
            "config": {"version": "7.10", "nodes": 3, "storage": "100Gi"},
        },
    }


@pytest.fixture
def managedservicelist_model_mock(managedservice_model_mock):
    return {
        "metadata": {
            "continue": 1,
        },
        "items": [managedservice_model_mock],
    }


@pytest.fixture
def managedservicebindinglist_model_mock(managedservice_binding_model_mock):
    return {
        "metadata": {
            "continue": 1,
        },
        "items": [managedservice_binding_model_mock],
    }


@pytest.fixture
def managedservice_binding_model_mock():
    return {
        "apiVersion": "api.rapyuta.io/v2",
        "kind": "ManagedServiceBinding",
        "metadata": {
            "guid": "mock_instance_binding_guid",
            "name": "test-instance-binding",
            "creatorGUID": "creator-guid",
            "projectGUID": "project-aaaaaaaaaaaaaaaaaaaa",
            "labels": {"env": "test"},
        },
        "spec": {
            "provider": "headscalevpn",
            "config": {"version": "1.0"},
        },
    }


# -------------------- CONFIGURATION --------------------


@pytest.fixture
def mock_config():
    return {
        "project_id": "mock_project_guid",
        "organization_id": "mock_org_guid",
        "auth_token": "mock_auth_token",
    }


@pytest.fixture
def config_obj():
    return Configuration(
        project_guid="mock_project_guid",
        organization_guid="mock_org_guid",
        auth_token="mock_auth_token",
    )
