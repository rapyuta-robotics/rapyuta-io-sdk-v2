import pytest

from rapyuta_io_sdk_v2 import Configuration


@pytest.fixture
def mock_response_user():
    return {
        "kind": "User",
        "metadata": {"name": "test user", "guid": "mock_user_guid"},
        "spec": {
            "firstName": "test",
            "lastName": "user",
            "emailID": "test.user@rapyuta-robotics.com",
            "projects": [
                {
                    "guid": "mock_project_guid",
                    "creator": "mock_user_guid",
                    "name": "test-project",
                    "organizationGUID": "mock_org_guid",
                    "organizationCreatorGUID": "mock_user_guid",
                },
            ],
            "organizations": [
                {
                    "guid": "mock_org_guid",
                    "name": "test-org",
                    "creator": "mock_user_guid",
                    "shortGUID": "abcde",
                },
            ],
        },
    }


@pytest.fixture
def user_body():
    return {
        "kind": "User",
        "metadata": {"name": "test user", "guid": "mock_user_guid"},
        "spec": {
            "firstName": "test",
            "lastName": "user",
            "emailID": "test.user@rapyuta-robotics.com",
        },
    }


@pytest.fixture
def mock_response_organization():
    return {
        "kind": "Organization",
        "metadata": {"name": "test-org", "guid": "mock_org_guid"},
        "spec": {
            "users": [
                {
                    "guid": "mock_user1_guid",
                    "emailID": "test.user1@rapyuta-robotics.com",
                    "roleInOrganization": "viewer",
                },
                {
                    "guid": "mock_user2_guid",
                    "emailID": "test.user2@rapyuta-robotics.com",
                    "roleInOrganization": "admin",
                },
            ]
        },
    }


@pytest.fixture
def organization_body():
    return {
        "kind": "Organization",
        "metadata": {"name": "test-org", "guid": "mock_org_guid"},
        "spec": {
            "users": [
                {
                    "guid": "mock_user1_guid",
                    "emailID": "test.user1@rapyuta-robotics.com",
                    "roleInOrganization": "viewer",
                },
                {
                    "guid": "mock_user2_guid",
                    "emailID": "test.user2@rapyuta-robotics.com",
                    "roleInOrganization": "admin",
                },
            ]
        },
    }


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
            "users": [{"emailID": "test.user@example.com", "role": "admin"}],
            "features": {"vpn": {"enabled": False}},
        },
    }


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
def deployment_body():
    return {
        "apiVersion": "apiextensions.rapyuta.io/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "test-deployment",
            "depends": {
                "kind": "Package",
                "nameOrGUID": "mock_package_guid",
            },
        },
        "restart": "Always",
    }


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
def network_body():
    return {
        "apiVersion": "apiextensions.rapyuta.io/v1",
        "kind": "Network",
        "metadata": {
            "name": "test-network",
            "region": "jp",
            "labels": {"app": "test"},
        },
    }


@pytest.fixture
def secret_body():
    return {
        "apiVersion": "apiextensions.rapyuta.io/v1",
        "kind": "Secret",
        "metadata": {
            "name": "test-secret",
            "labels": {"app": "test"},
        },
    }


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


@pytest.fixture
def mock_config():
    return Configuration(
        project_guid="mock_project_guid",
        organization_guid="mock_org_guid",
        auth_token="mock_auth_token",
    )
