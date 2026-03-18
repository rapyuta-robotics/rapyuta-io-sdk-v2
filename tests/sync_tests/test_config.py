import json

# ruff: noqa: F811, F401

import pytest
from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.constants import STAGING_ENVIRONMENT_SUBDOMAIN
from rapyuta_io_sdk_v2.exceptions import ValidationError
from tests.data.mock_data import mock_config, config_obj


def test_from_file(mocker, mock_config):
    mock_file_content = json.dumps(mock_config)

    # Mock the open function
    mocker.patch("builtins.open", mocker.mock_open(read_data=mock_file_content))

    # Mock the default directory function
    mocker.patch(
        "rapyuta_io_sdk_v2.config.get_default_app_dir", return_value="/mock/default/dir"
    )

    # Call the method to test
    config = Configuration.from_file(file_path="/mock/path/to/config.json")

    # Assert the Configuration object contains the expected values
    assert config.project_guid == mock_config["project_id"]
    assert config.organization_guid == mock_config["organization_id"]
    assert config.auth_token == mock_config["auth_token"]


def test_get_headers_basic(config_obj):
    # Call the method without passing any arguments
    headers = config_obj.get_headers()

    # Verify the headers
    assert headers["Authorization"] == "Bearer mock_auth_token"
    assert headers["organizationguid"] == "mock_org_guid"
    assert headers["project"] == "mock_project_guid"


def test_get_headers_without_project(config_obj):
    # Call the method with `with_project=False`
    headers = config_obj.get_headers(with_project=False)

    # Verify the headers
    assert headers["Authorization"] == "Bearer mock_auth_token"
    assert headers["organizationguid"] == "mock_org_guid"
    assert "project" not in headers


def test_get_headers_with_custom_values(config_obj):
    # Call the method with custom organization_guid and project_guid
    headers = config_obj.get_headers(
        organization_guid="custom_org_guid",
        project_guid="custom_project_guid",
    )

    # Verify the headers
    assert headers["Authorization"] == "Bearer mock_auth_token"
    assert headers["organizationguid"] == "custom_org_guid"
    assert headers["project"] == "custom_project_guid"


def test_get_headers_with_request_id(mocker, config_obj):
    # Mock the environment variable
    mocker.patch("os.getenv", return_value="mock_request_id")

    # Call the method
    headers = config_obj.get_headers()

    # Verify the headers
    assert headers["Authorization"] == "Bearer mock_auth_token"
    assert headers["organizationguid"] == "mock_org_guid"
    assert headers["project"] == "mock_project_guid"
    assert headers["X-Request-ID"] == "mock_request_id"


# ---------------------------------------------------------------------------
# set_environment() — default hosts per environment
# ---------------------------------------------------------------------------


def test_set_environment_default_ga_hosts():
    # The default environment is "ga"; verify production hosts are applied.
    config = Configuration()
    assert config.hosts["environment"] == "ga"
    assert config.hosts["v2api_host"] == "https://api.rapyuta.io"
    assert config.hosts["rip_host"] == "https://garip.apps.okd4v2.prod.rapyuta.io"


def test_set_environment_explicit_ga_hosts():
    # Explicitly passing environment="ga" must produce the same production hosts.
    config = Configuration(environment="ga")
    assert config.hosts["environment"] == "ga"
    assert config.hosts["v2api_host"] == "https://api.rapyuta.io"
    assert config.hosts["rip_host"] == "https://garip.apps.okd4v2.prod.rapyuta.io"


def test_set_environment_qa_hosts():
    # "qa" is a named staging environment; hosts must use the staging subdomain.
    config = Configuration(environment="qa")
    assert config.hosts["environment"] == "qa"
    assert config.hosts["v2api_host"] == f"https://qaapi.{STAGING_ENVIRONMENT_SUBDOMAIN}"
    assert config.hosts["rip_host"] == f"https://qarip.{STAGING_ENVIRONMENT_SUBDOMAIN}"


def test_set_environment_dev_hosts():
    # "dev" is a named staging environment; hosts must use the staging subdomain.
    config = Configuration(environment="dev")
    assert config.hosts["environment"] == "dev"
    assert config.hosts["v2api_host"] == f"https://devapi.{STAGING_ENVIRONMENT_SUBDOMAIN}"
    assert config.hosts["rip_host"] == f"https://devrip.{STAGING_ENVIRONMENT_SUBDOMAIN}"


def test_set_environment_pr_hosts():
    # PR environments are identified by the "pr" prefix.
    config = Configuration(environment="pr123")
    assert config.hosts["environment"] == "pr123"
    assert (
        config.hosts["v2api_host"] == f"https://pr123api.{STAGING_ENVIRONMENT_SUBDOMAIN}"
    )
    assert config.hosts["rip_host"] == f"https://pr123rip.{STAGING_ENVIRONMENT_SUBDOMAIN}"


def test_set_environment_local_default_host():
    # "local" environment falls back to hardcoded defaults for both hosts
    # when neither instance fields nor env vars are set.
    config = Configuration(environment="local")
    assert config.hosts["environment"] == "local"
    assert config.hosts["v2api_host"] == "http://gateway/io"
    assert config.hosts["rip_host"] == "http://rip"


def test_set_environment_local_env_var_override(monkeypatch):
    # LOCAL_V2API_HOST overrides the v2api default; rip falls back to "http://rip".
    monkeypatch.setenv("LOCAL_V2API_HOST", "http://localhost:8080")
    config = Configuration(environment="local")
    assert config.hosts["environment"] == "local"
    assert config.hosts["v2api_host"] == "http://localhost:8080"
    assert config.hosts["rip_host"] == "http://rip"


def test_set_environment_local_rip_env_var_override(monkeypatch):
    # LOCAL_RIP_HOST overrides the rip default; v2api falls back to "http://gateway/io".
    monkeypatch.setenv("LOCAL_RIP_HOST", "http://localhost:9090")
    config = Configuration(environment="local")
    assert config.hosts["environment"] == "local"
    assert config.hosts["v2api_host"] == "http://gateway/io"
    assert config.hosts["rip_host"] == "http://localhost:9090"


def test_set_environment_local_both_env_vars_override(monkeypatch):
    # Both LOCAL_V2API_HOST and LOCAL_RIP_HOST override the hardcoded defaults.
    monkeypatch.setenv("LOCAL_V2API_HOST", "http://localhost:8080")
    monkeypatch.setenv("LOCAL_RIP_HOST", "http://localhost:9090")
    config = Configuration(environment="local")
    assert config.hosts["environment"] == "local"
    assert config.hosts["v2api_host"] == "http://localhost:8080"
    assert config.hosts["rip_host"] == "http://localhost:9090"


def test_set_environment_none_defaults_to_ga():
    # Passing None to set_environment() must be treated identically to "ga".
    config = Configuration(environment="ga")
    config.set_environment(None)
    assert config.hosts["environment"] == "ga"
    assert config.hosts["v2api_host"] == "https://api.rapyuta.io"
    assert config.hosts["rip_host"] == "https://garip.apps.okd4v2.prod.rapyuta.io"


# ---------------------------------------------------------------------------
# set_environment() — user-supplied hosts take priority over env defaults
# ---------------------------------------------------------------------------


def test_custom_v2api_host_used_over_ga_default():
    # v2_api_host on the instance is used instead of the "ga" default.
    config = Configuration(environment="ga", v2_api_host="https://custom.api.example.com")
    assert config.hosts["v2api_host"] == "https://custom.api.example.com"
    # rip_host was not supplied so the environment default applies.
    assert config.hosts["rip_host"] == "https://garip.apps.okd4v2.prod.rapyuta.io"


def test_custom_rip_host_used_over_ga_default():
    # rip_host on the instance is used instead of the "ga" default.
    config = Configuration(environment="ga", rip_host="https://custom.rip.example.com")
    assert config.hosts["rip_host"] == "https://custom.rip.example.com"
    # v2api_host was not supplied so the environment default applies.
    assert config.hosts["v2api_host"] == "https://api.rapyuta.io"


def test_both_custom_hosts_used_over_ga_defaults():
    # Both hosts supplied — neither is overwritten by the environment logic.
    config = Configuration(
        environment="ga",
        v2_api_host="https://custom.api.example.com",
        rip_host="https://custom.rip.example.com",
    )
    assert config.hosts["v2api_host"] == "https://custom.api.example.com"
    assert config.hosts["rip_host"] == "https://custom.rip.example.com"


def test_custom_v2api_host_used_over_staging_default():
    # Custom v2_api_host is also honoured for staging environments.
    config = Configuration(environment="qa", v2_api_host="https://custom.api.example.com")
    assert config.hosts["v2api_host"] == "https://custom.api.example.com"
    # rip_host was not supplied; staging default applies.
    assert config.hosts["rip_host"] == f"https://qarip.{STAGING_ENVIRONMENT_SUBDOMAIN}"


def test_custom_rip_host_used_over_staging_default():
    # rip_host supplied at construction is used instead of the staging computed default.
    config = Configuration(environment="qa", rip_host="https://custom.rip.example.com")
    assert config.hosts["rip_host"] == "https://custom.rip.example.com"
    # v2api_host was not supplied; staging default applies.
    assert config.hosts["v2api_host"] == f"https://qaapi.{STAGING_ENVIRONMENT_SUBDOMAIN}"


def test_custom_rip_host_preserved_across_staging_environment_switch():
    # rip_host set on the instance must survive a call to set_environment() that
    # targets a different staging environment; only the default slot for the new
    # environment name should change, not the user-supplied value.
    config = Configuration(environment="qa", rip_host="https://custom.rip.example.com")
    assert config.hosts["rip_host"] == "https://custom.rip.example.com"

    config.set_environment("pr99")

    assert config.hosts["environment"] == "pr99"
    assert config.hosts["rip_host"] == "https://custom.rip.example.com"
    # v2api_host was not supplied; it must be recomputed for the new environment.
    assert (
        config.hosts["v2api_host"] == f"https://pr99api.{STAGING_ENVIRONMENT_SUBDOMAIN}"
    )


def test_custom_v2api_host_used_over_local_default():
    # Custom v2_api_host is honoured for the "local" environment; rip falls back to "http://rip".
    config = Configuration(environment="local", v2_api_host="http://localhost:9000")
    assert config.hosts["v2api_host"] == "http://localhost:9000"
    assert config.hosts["rip_host"] == "http://rip"


def test_custom_rip_host_used_over_local_default():
    # Custom rip_host is honoured for the "local" environment; v2api falls back to "http://gateway/io".
    config = Configuration(environment="local", rip_host="http://localhost:9091")
    assert config.hosts["rip_host"] == "http://localhost:9091"
    assert config.hosts["v2api_host"] == "http://gateway/io"


def test_whitespace_only_host_treated_as_not_provided():
    # A whitespace-only string is normalised to None in __post_init__,
    # so the environment default is applied as if no host were given.
    config = Configuration(environment="ga", v2_api_host="   ")
    assert config.hosts["v2api_host"] == "https://api.rapyuta.io"


# ---------------------------------------------------------------------------
# set_environment() — switching environments after construction
# ---------------------------------------------------------------------------


def test_switch_environment_updates_environment_key():
    # The "environment" key in hosts is always updated on each call.
    config = Configuration(environment="ga")
    assert config.hosts["environment"] == "ga"

    config.set_environment("dev")
    assert config.hosts["environment"] == "dev"

    config.set_environment("pr42")
    assert config.hosts["environment"] == "pr42"


def test_switch_environment_recomputes_default_hosts():
    # Switching environment recomputes host URLs to the new environment's
    # defaults when no user-supplied hosts are set on the instance.
    config = Configuration(environment="ga")
    assert config.hosts["v2api_host"] == "https://api.rapyuta.io"
    assert config.hosts["rip_host"] == "https://garip.apps.okd4v2.prod.rapyuta.io"

    config.set_environment("dev")

    assert config.hosts["environment"] == "dev"
    assert config.hosts["v2api_host"] == f"https://devapi.{STAGING_ENVIRONMENT_SUBDOMAIN}"
    assert config.hosts["rip_host"] == f"https://devrip.{STAGING_ENVIRONMENT_SUBDOMAIN}"


def test_switch_environment_from_ga_to_staging():
    # Switching from "ga" to "qa" updates both host URLs.
    config = Configuration(environment="ga")
    assert config.hosts["v2api_host"] == "https://api.rapyuta.io"

    config.set_environment("qa")

    assert config.hosts["environment"] == "qa"
    assert config.hosts["v2api_host"] == f"https://qaapi.{STAGING_ENVIRONMENT_SUBDOMAIN}"
    assert config.hosts["rip_host"] == f"https://qarip.{STAGING_ENVIRONMENT_SUBDOMAIN}"


def test_switch_environment_preserves_user_host():
    # When v2_api_host is set on the instance it is preserved across environment
    # switches; the unpinned rip_host is recomputed for the new environment.
    config = Configuration(environment="ga", v2_api_host="https://custom.api.example.com")
    assert config.hosts["v2api_host"] == "https://custom.api.example.com"

    config.set_environment("qa")

    assert config.hosts["environment"] == "qa"
    assert config.hosts["v2api_host"] == "https://custom.api.example.com"
    assert config.hosts["rip_host"] == f"https://qarip.{STAGING_ENVIRONMENT_SUBDOMAIN}"


# ---------------------------------------------------------------------------
# set_environment() — validation
# ---------------------------------------------------------------------------


def test_set_environment_invalid_raises_validation_error():
    # An entirely unknown environment name must raise ValidationError.
    with pytest.raises(ValidationError):
        Configuration(environment="invalid_env")


def test_set_environment_invalid_direct_call_raises_validation_error():
    # Calling set_environment() directly with a bad name must also raise.
    config = Configuration(environment="ga")
    with pytest.raises(ValidationError):
        config.set_environment("not_a_valid_env")
