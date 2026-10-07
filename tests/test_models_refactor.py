"""Contracts for Python field names and the unchanged platform JSON schema."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
from datetime import datetime, UTC

import pytest
from pydantic import BaseModel

import rapyuta_io_sdk_v2.models as models
from rapyuta_io_sdk_v2.models.configtree import ConfigTree, ConfigTreeKeyUpdate
from rapyuta_io_sdk_v2.models.deployment import Deployment
from rapyuta_io_sdk_v2.models.network import Network
from rapyuta_io_sdk_v2.models.oauth2 import OAuth2ClientCreate, OAuth2UpdateURI
from rapyuta_io_sdk_v2.models.package import Package
from rapyuta_io_sdk_v2.models.rolebinding import BulkRoleBindingResponse
from rapyuta_io_sdk_v2.models.utils import (
    BaseList,
    BaseMetadata,
    PackageDepends,
    SDKModel,
    resource_key,
)
from tests.data import mock_data


def test_every_data_model_has_snake_case_fields_and_shared_configuration():
    found = 0
    for module in pkgutil.iter_modules(models.__path__):
        imported = importlib.import_module(f"{models.__name__}.{module.name}")
        for _, cls in inspect.getmembers(imported, inspect.isclass):
            if cls.__module__ != imported.__name__ or not issubclass(cls, BaseModel):
                continue
            found += 1
            assert all(
                re.fullmatch(r"[a-z][a-z0-9_]*", name) for name in cls.model_fields
            ), cls
            if not cls.__pydantic_root_model__:
                assert issubclass(cls, SDKModel), cls
                assert cls.model_config["populate_by_name"], cls
    assert found > 100


def test_metadata_names_aliases_timestamps_and_user_keys():
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    snake = BaseMetadata(
        name="sample",
        project_guid="project",
        organization_creator_guid="creator",
        created_at=timestamp,
        labels={"camelCase/UserKey": "value"},
    )
    wire = snake.model_dump(by_alias=True)
    assert wire["projectGUID"] == "project"
    assert wire["organizationCreatorGUID"] == "creator"
    assert wire["createdAt"] == timestamp.isoformat()
    assert wire["labels"] == {"camelCase/UserKey": "value"}
    assert BaseMetadata.model_validate(wire) == snake


@pytest.mark.parametrize("input_name", ["name_or_guid", "nameOrGUID", "nameOrGuid"])
def test_dependency_accepts_python_name_and_both_server_spellings(input_name):
    dependency = PackageDepends.model_validate({input_name: "pkg", "version": "v1"})
    assert dependency.model_dump(by_alias=True)["nameOrGUID"] == "pkg"


def test_lists_always_have_independent_usable_items():
    first = BaseList[int]()
    first.items.append(1)
    assert BaseList[int]().items == []
    assert BaseList[int].model_validate({"items": None}).items == []
    assert (
        BaseList[int](api_version="api.rapyuta.io/v2").model_dump(by_alias=True)[
            "apiVersion"
        ]
        == "api.rapyuta.io/v2"
    )


def test_deep_package_aliases_constructible_by_python_names():
    package = Package.model_validate(
        {
            "metadata": {"name": "pkg", "version": "v1"},
            "spec": {
                "runtime": "cloud",
                "host_pid": True,
                "environment_vars": [
                    {
                        "name": "TOKEN",
                        "value_from": {
                            "secret_key_ref": {"name": "secret", "key": "camelCase/Key"}
                        },
                        "exposed_name": "TOKEN",
                    }
                ],
                "executables": [
                    {
                        "name": "main",
                        "docker": {"image": "image", "image_pull_policy": "Always"},
                        "liveness_probe": {
                            "http_get": {
                                "path": "/",
                                "port": 80,
                                "http_headers": [{"name": "X-Case", "value": "value"}],
                            },
                            "timeout_seconds": 10,
                        },
                    }
                ],
                "endpoints": [
                    {"name": "http", "target_port": 8080, "port_range": "1000-1001"}
                ],
                "ros": {"ros_endpoints": [{"type": "topic", "name": "/topic"}]},
            },
        }
    )
    wire = package.model_dump(by_alias=True, exclude_none=True)
    assert wire["spec"]["hostPID"] is True
    assert (
        wire["spec"]["environmentVars"][0]["valueFrom"]["secretKeyRef"]["key"]
        == "camelCase/Key"
    )
    assert wire["spec"]["executables"][0]["docker"]["imagePullPolicy"] == "Always"
    assert (
        wire["spec"]["executables"][0]["livenessProbe"]["httpGet"]["httpHeaders"][0][
            "name"
        ]
        == "X-Case"
    )
    assert wire["spec"]["endpoints"][0]["targetPort"] == 8080
    assert wire["spec"]["ros"]["rosEndpoints"][0]["name"] == "/topic"
    assert Package.model_validate(wire) == package


def test_deployment_aliases_and_versioned_dependencies():
    deployment = Deployment.model_validate(
        {
            "metadata": {
                "name": "deployment",
                "depends": {"name_or_guid": "pkg", "version": "v2"},
            },
            "spec": {
                "runtime": "cloud",
                "env_args": [
                    {
                        "name": "SECRET",
                        "value_from": {"secret_key_ref": {"name": "secret"}},
                    }
                ],
                "ros_networks": [
                    {"depends": {"name_or_guid": "network"}, "domain_id": 5}
                ],
                "static_routes": [{"depends": {"name_or_guid": "route"}}],
                "service_account": "account",
                "network_interface": "eth0",
                "features": {"params": {"block_until_synced": True}},
            },
        }
    )
    wire = deployment.model_dump(by_alias=True, exclude_none=True)
    assert wire["spec"]["envArgs"][0]["valueFrom"]["secretKeyRef"]["name"] == "secret"
    assert wire["spec"]["rosNetworks"][0]["domainID"] == 5
    assert wire["spec"]["features"]["params"]["blockUntilSynced"] is True
    assert wire["spec"]["networkInterface"] == "eth0"
    assert resource_key("Package", "pkg", "v2") in deployment.list_dependencies()
    assert resource_key("Package", "pkg", "v1") != resource_key("Package", "pkg", "v2")
    with pytest.raises(ValueError, match="version"):
        resource_key("Package", "pkg")


@pytest.mark.parametrize(
    "cls,fixture",
    [
        (Package, "cloud_package_model_mock"),
        (Package, "device_package_model_mock"),
        (Deployment, "cloud_deployment_model_mock"),
        (Deployment, "device_deployment_model_mock"),
        (Network, "network_model_mock"),
    ],
)
def test_existing_deep_wire_fixtures_keep_original_keys(cls, fixture):
    payload = getattr(mock_data, fixture).__wrapped__()
    result = cls.model_validate(payload).model_dump(by_alias=True)

    def check_keys(original, emitted):
        if isinstance(original, dict):
            for key, value in original.items():
                assert key in emitted, key
                check_keys(value, emitted[key])
        elif isinstance(original, list):
            for old, new in zip(original, emitted, strict=True):
                check_keys(old, new)
        else:
            assert emitted == original

    check_keys(payload, result)


def test_configtree_paths_and_opaque_response_data_are_preserved():
    tree = ConfigTree.model_validate(
        {
            "metadata": {"name": "tree"},
            "keys": {
                "SomeCase/path": {
                    "contentType": "kv",
                    "data": "MQ==",
                    "vendorData": {"SomeCase": 2},
                }
            },
        }
    )
    assert tree.keys["SomeCase/path"].content_type == "kv"
    assert tree.model_dump(by_alias=True)["keys"]["SomeCase/path"]["vendorData"] == {
        "SomeCase": 2
    }
    update = ConfigTreeKeyUpdate.model_validate(
        {"SomeCase/path": {"content_type": "kv", "data": "MQ=="}}
    )
    assert update.model_dump(by_alias=True, exclude_unset=True) == {
        "SomeCase/path": {"contentType": "kv", "data": "MQ=="}
    }
    opaque = {"vendorResponse": [{"camelCase/Key": "value"}]}
    assert BulkRoleBindingResponse.model_validate(opaque).model_dump() == opaque


def test_oauth_body_keys_match_the_specific_endpoint():
    standard = OAuth2ClientCreate(
        client_name="client",
        redirect_uris=["https://example.test"],
        metadata={"SomeCase": True},
    )
    assert standard.model_dump(by_alias=True, exclude_unset=True) == {
        "client_name": "client",
        "redirect_uris": ["https://example.test"],
        "metadata": {"SomeCase": True},
    }
    uris = OAuth2UpdateURI(
        redirect_uris=["https://example.test"], post_logout_redirect_uris=None
    )
    assert uris.model_dump(by_alias=True) == {
        "redirectURIs": ["https://example.test"],
        "postLogoutRedirectURIs": None,
    }
