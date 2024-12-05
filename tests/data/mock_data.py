import pytest

from rapyuta_io_sdk_v2 import Configuration


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
