"""Configuration source precedence and request scope contracts."""

import json

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsError

from rapyuta_io_sdk_v2 import Configuration, FeatureFlags, RequestContext
from rapyuta_io_sdk_v2.features import (
    FeatureDisabledError,
    MissingOptionalDependencyError,
)
from rapyuta_io_sdk_v2.features import require_dependency


def test_cli_keys_and_source_priority(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "email_id": "a@example.com",
                "project_id": "file-project",
                "organization_id": "file-org",
                "auth_token": "file-token",
                "v2api_host": "https://file.test",
                "rip_host": "https://auth.test",
                "environment": "qa",
                "unrelated_cli_setting": True,
            }
        )
    )
    monkeypatch.setenv("RIO_CONFIG", str(path))
    monkeypatch.setenv("RIO_PROJECT_GUID", "env-project")
    config = Configuration(organization_guid="explicit-org")
    assert isinstance(config, BaseSettings)
    assert config.email == "a@example.com"
    assert config.project_guid == "env-project"
    assert config.organization_guid == "explicit-org"
    assert config.auth_token == "file-token"
    assert config.resolved_v2_api_host == "https://file.test"
    assert config.resolved_rip_host == "https://auth.test"
    assert config.environment == "qa"
    assert "file-token" not in repr(config)
    assert not hasattr(config, "hosts")


def test_explicit_file_overrides_rio_config(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text('{"project_id":"explicit-file"}')
    monkeypatch.setenv("RIO_CONFIG", str(tmp_path / "missing.json"))
    assert Configuration(config_file=path).project_guid == "explicit-file"


def test_missing_default_file_is_optional(tmp_path, monkeypatch):
    monkeypatch.delenv("RIO_CONFIG", raising=False)
    monkeypatch.delenv("RIO_CONFIG_FILE", raising=False)
    monkeypatch.setattr(
        "rapyuta_io_sdk_v2.config.get_default_app_dir", lambda _: str(tmp_path)
    )
    assert Configuration().environment == "ga"


@pytest.mark.parametrize("contents", [None, "{", "[]", '"not a mapping"'])
def test_explicit_invalid_config_fails(tmp_path, contents):
    path = tmp_path / "config.json"
    if contents is not None:
        path.write_text(contents)
    with pytest.raises((SettingsError, ValidationError)):
        Configuration(config_file=path)


def test_file_loading_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("RIO_CONFIG", str(tmp_path / "missing"))
    config = Configuration(load_cli_config=False, auth_token="constructor")
    assert config.auth_token == "constructor"
    monkeypatch.setenv("RIO_LOAD_CLI_CONFIG", "false")
    assert Configuration().environment == "ga"


@pytest.mark.parametrize(
    "environment,v2,rip",
    [
        ("ga", "https://api.rapyuta.io", "https://garip.apps.okd4v2.prod.rapyuta.io"),
        ("local", "http://gateway/io", "http://rip"),
        (
            "qa",
            "https://qaapi.apps.okd4v2.okd4beta.rapyuta.io",
            "https://qarip.apps.okd4v2.okd4beta.rapyuta.io",
        ),
        (
            "pr123",
            "https://pr123api.apps.okd4v2.okd4beta.rapyuta.io",
            "https://pr123rip.apps.okd4v2.okd4beta.rapyuta.io",
        ),
    ],
)
def test_environment_hosts(environment, v2, rip, monkeypatch):
    monkeypatch.delenv("LOCAL_V2API_HOST", raising=False)
    monkeypatch.delenv("LOCAL_RIP_HOST", raising=False)
    config = Configuration(load_cli_config=False, environment=environment)
    assert config.resolved_v2_api_host == v2
    assert config.resolved_rip_host == rip


def test_hosts_recompute_and_overrides_survive():
    config = Configuration(load_cli_config=False, v2_api_host=" https://override.test/ ")
    config.environment = "qa"
    assert config.resolved_v2_api_host == "https://override.test"
    assert config.resolved_rip_host.startswith("https://qarip.")
    config.rip_host = " "
    assert config.rip_host is None
    with pytest.raises(ValidationError):
        config.environment = "bad"
    assert config.environment == "qa"


def test_local_environment_overrides(monkeypatch):
    monkeypatch.setenv("LOCAL_V2API_HOST", "http://localhost:8080")
    monkeypatch.setenv("LOCAL_RIP_HOST", "http://localhost:9090")
    config = Configuration(load_cli_config=False, environment="local")
    assert config.resolved_v2_api_host == "http://localhost:8080"
    assert config.resolved_rip_host == "http://localhost:9090"


def test_nested_feature_environment_and_constructor_priority(monkeypatch):
    monkeypatch.setenv("RIO_FEATURES__APPLY", "true")
    config = Configuration(load_cli_config=False)
    assert config.features.apply
    config = Configuration(load_cli_config=False, features={"apply": False})
    assert not config.features.apply
    with pytest.raises(ValidationError, match="requires"):
        FeatureFlags(charts=True)


def test_feature_and_dependency_errors():
    with pytest.raises(FeatureDisabledError, match="features.apply"):
        FeatureFlags().require("apply")
    with pytest.raises(MissingOptionalDependencyError, match=r"\[apply\]"):
        require_dependency("missing_sdk_test_dependency", "apply")


@pytest.mark.parametrize("token", [" token ", "Bearer token", "bearer token"])
def test_request_context_is_per_request(token, monkeypatch):
    monkeypatch.setenv("REQUEST_ID", "request-id")
    config = Configuration(
        load_cli_config=False,
        auth_token=token,
        organization_guid="org",
        project_guid="project",
    )
    headers = config.get_headers(
        context=RequestContext(
            project_guid="override",
            with_organization=False,
            x_checksum="checksum",
            content_type="application/json",
            headers={"X-Test": "value"},
        )
    )
    assert headers["Authorization"].lower() == "bearer token"
    assert headers["project"] == "override"
    assert "organizationguid" not in headers
    assert headers["X-Request-ID"] == "request-id"
    assert headers["X-Checksum"] == "checksum"
    assert headers["X-Test"] == "value"
    assert config.project_guid == "project"
    assert config.get_headers()["project"] == "project"


def test_failed_feature_assignment_preserves_valid_state():
    flags = FeatureFlags()
    with pytest.raises(ValidationError):
        flags.charts = True
    assert flags.charts is False
    flags.apply = True
    flags.charts = True
    with pytest.raises(ValidationError):
        flags.apply = False
    assert flags.apply is True
