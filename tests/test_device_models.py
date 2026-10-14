# Copyright 2026 Rapyuta Robotics
import pytest
from pydantic import ValidationError

from rapyuta_io_sdk_v2 import models
from tests.data.device_data import DEVICE, TOKEN, VPN


@pytest.mark.parametrize("report", ["healthy", []])
def test_device_rejects_invalid_daemon_report(report: object) -> None:
    with pytest.raises(ValidationError):
        models.Device.model_validate({**DEVICE, "daemons_status": report})


@pytest.mark.parametrize("name", ["ab", "1abc", "robot_", "robot-", "a" * 257])
def test_registration_rejects_invalid_name(name: str) -> None:
    with pytest.raises(ValidationError):
        models.DeviceCreate(name=name, config_variables={"runtime_docker": True})


def test_registration_preserves_runtime_and_unicode_name() -> None:
    body = models.DeviceCreate(
        name="robot élite", config_variables={"runtime_docker": "True"}
    )
    assert body.name == "robot élite"
    assert body.config_variables.root["runtime_docker"] == "True"


@pytest.mark.parametrize(
    "payload", [{}, {"name": None}, {"status": "NEW"}, {"device_id": "other"}]
)
def test_invalid_update(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        models.DeviceUpdate.model_validate(payload)


def test_token_repr_is_redacted() -> None:
    result = models.DeviceRegistrationResponse.model_validate(TOKEN)
    assert result.response.data == "fixture-onboarding-token"
    assert result.response.data not in repr(result)


def test_selection_leaf_and_empty_logical_rules() -> None:
    models.DeviceSelection(operator="$or", labels={"operator": "$and", "args": []})
    with pytest.raises(ValidationError):
        models.DeviceSelection(operator="$or", specs={"operator": "$and", "args": []})
    with pytest.raises(ValidationError):
        models.DeviceSelection(
            operator="$or", labels={"operator": "$eq", "args": ["one"]}
        )


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        ("DeviceLabelUpdate", {}),
        ("DeviceLabelUpdate", {"key": None}),
        ("DeviceLabelsCreate", {"bad key": "value"}),
        ("DeviceConfigVariableCreate", {"key": "key", "value": ""}),
        ("DeviceConfigVariableUpdate", {"key": "rename", "value": "x"}),
        ("DeviceVPNUpdate", {"vpn": "false"}),
        (
            "DeviceVPNUpdate",
            {"vpn": False, "config": {"vpn": {"advertise_routes": True}}},
        ),
        ("DeviceVPNUpdate", {"vpn": True, "tracing": True}),
        ("DeviceParameterApply", {"device_list": []}),
        ("DeviceParameterApply", {"device_list": ["a", "a"]}),
        ("DeviceMigration", {"project": " "}),
    ],
)
def test_management_constraints(model: str, payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        getattr(models, model).model_validate(payload)


def test_vpn_daemon_fields_and_defaults() -> None:

    body = models.DeviceVPNUpdate(vpn=True, config={"vpn": {}})
    assert body.config.vpn.advertise_routes is False
    result = models.DeviceVPNResponse.model_validate(
        {"status": "success", "response": {"data": VPN}}
    )
    daemon = result.response.data
    assert daemon.kind == "DeviceDaemon"
    assert daemon.spec.ssh_cert_config.enable is True
    assert daemon.spec.pull_secret.auth == "fake-encoded-auth"
    assert "fake-encoded-auth" not in repr(daemon)
