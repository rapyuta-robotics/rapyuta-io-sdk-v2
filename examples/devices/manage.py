# Copyright 2026 Rapyuta Robotics
"""Manage explicit device targets using Configuration's environment/context.

Registration/onboarding return authorization, whose token is never printed or
installed. Empty/null update descriptions are service no-ops. Use returned
label/config record IDs for edits. VPN acceptance does not imply connectivity
readiness. Migration retains source authorization and has no VPN side effects.
"""

from __future__ import annotations

import argparse

from examples.devices._configuration import configuration
from rapyuta_io_sdk_v2 import Client, models

ACTIONS = (
    "list",
    "select",
    "create",
    "onboarding",
    "get",
    "update",
    "delete",
    "label-list",
    "label-create",
    "label-update",
    "label-delete",
    "config-list",
    "config-create",
    "config-update",
    "config-delete",
    "vpn-enable",
    "vpn-disable",
    "parameters",
    "migrate",
)


def parser() -> argparse.ArgumentParser:
    """Build explicit lifecycle and management options."""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("action", choices=ACTIONS)
    for flag in (
        "device",
        "name",
        "description",
        "status",
        "selection",
        "key",
        "value",
        "destination-project",
    ):
        result.add_argument("--" + flag)
    result.add_argument(
        "--record-id", type=int, help="ID returned by label/config creation or listing"
    )
    result.add_argument(
        "--advertise-routes",
        action="store_true",
        help="Use project-configured VPN routes",
    )
    result.add_argument(
        "--target",
        action="append",
        help="Explicit Parameter target; repeat for multiple devices",
    )
    result.add_argument(
        "--tree", action="append", help="Parameter tree; omitted means all"
    )
    return result


def operation(args: argparse.Namespace) -> tuple[str, tuple[object, ...]]:
    """Build one typed operation from explicit command-line input.

    Args:
        args: Selected action and operation inputs.
    """
    builders = {
        "list": lambda: ("list_devices", ()),
        "select": lambda: (
            "select_devices",
            (models.DeviceSelection.model_validate_json(args.selection),),
        ),
        "create": lambda: (
            "create_device",
            (
                models.DeviceCreate(
                    name=args.name,
                    config_variables={"runtime_docker": True},
                    description=args.description,
                ),
            ),
        ),
        "onboarding": lambda: ("get_device_onboarding", (args.device,)),
        "get": lambda: ("get_device", (args.device,)),
        "update": lambda: ("update_device", (args.device, _update(args))),
        "delete": lambda: ("delete_device", (args.device,)),
        "label-list": lambda: ("list_device_labels", (args.device,)),
        "label-create": lambda: (
            "create_device_labels",
            (args.device, models.DeviceLabelsCreate({args.key: args.value})),
        ),
        "label-update": lambda: (
            "update_device_label",
            (args.record_id, models.DeviceLabelUpdate(value=args.value)),
        ),
        "label-delete": lambda: ("delete_device_label", (args.record_id,)),
        "config-list": lambda: ("list_device_config_variables", (args.device,)),
        "config-create": lambda: (
            "create_device_config_variable",
            (
                args.device,
                models.DeviceConfigVariableCreate(key=args.key, value=args.value),
            ),
        ),
        "config-update": lambda: (
            "update_device_config_variable",
            (args.record_id, models.DeviceConfigVariableUpdate(value=args.value)),
        ),
        "config-delete": lambda: ("delete_device_config_variable", (args.record_id,)),
        "vpn-enable": lambda: ("set_device_vpn", (args.device, _vpn(args))),
        "vpn-disable": lambda: ("set_device_vpn", (args.device, _vpn(args))),
        "parameters": lambda: (
            "apply_device_parameters",
            (
                models.DeviceParameterApply(
                    device_list=tuple(args.target or [args.device]),
                    tree_names=tuple(args.tree or ()),
                ),
            ),
        ),
        "migrate": lambda: (
            "migrate_device",
            (args.device, models.DeviceMigration(project=args.destination_project)),
        ),
    }
    return builders[args.action]()


def _update(args: argparse.Namespace) -> models.DeviceUpdate:
    fields = {
        key: getattr(args, key)
        for key in ("name", "description", "status")
        if getattr(args, key) is not None
    }
    return models.DeviceUpdate.model_validate(fields)


def _vpn(args: argparse.Namespace) -> models.DeviceVPNUpdate:
    return models.DeviceVPNUpdate(
        vpn=args.action == "vpn-enable",
        config=models.DeviceVPNConfiguration(
            vpn=models.DeviceVPNRouteConfiguration(
                advertise_routes=args.advertise_routes
            )
        ),
    )


def invoke(client: Client, args: argparse.Namespace) -> object:
    """Perform one operation; discovery and prechecks are never implicit.

    Args:
        client: Caller-owned configured client.
        args: Selected operation inputs.
    """
    if args.action == "list":
        return client.list_devices(query=models.DeviceListQuery(name=args.name))
    method, values = operation(args)
    return getattr(client, method)(*values)


def report(result: object, args: argparse.Namespace) -> None:
    """Show typed records/daemon acknowledgment and missing Parameter targets.

    Args:
        result: Named operation response.
        args: Explicit targets supplied to the example.
    """
    print(result)
    if isinstance(result, models.DeviceParameterApplyResponse):
        reported = {item.device_id for item in result.response.data}
        print(
            "Targets omitted by service:",
            tuple(
                target
                for target in (args.target or [args.device])
                if target not in reported
            ),
        )


def main() -> None:
    """Release the transport owned by this example."""
    args = parser().parse_args()
    client = Client(configuration())
    try:
        report(invoke(client, args), args)
    finally:
        client.c.close()


if __name__ == "__main__":
    main()
