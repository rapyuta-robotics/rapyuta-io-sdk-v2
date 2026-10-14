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

"""CLI compatible filters for local Apply rendering."""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from functools import cache
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any

from jinja2 import StrictUndefined, pass_context
from jinja2.sandbox import ImmutableSandboxedEnvironment

if TYPE_CHECKING:
    from jinja2.runtime import Context

    from rapyuta_io_sdk_v2.apply.source import DeviceInterfaceResolver
    from rapyuta_io_sdk_v2.models.applier import ResourceScope


def _project_guid(scope: ResourceScope, rio: Mapping[str, Any]) -> str:
    guid = scope.project_guid
    if not guid:
        msg = "get_intf_ip requires ApplierOptions.scope.project_guid"
        raise ValueError(msg)
    project = rio.get("project")
    if isinstance(project, Mapping):
        rio_guid = project.get("guid")
        if rio_guid is not None and rio_guid != guid:
            msg = "rio.project.guid does not match ApplierOptions.scope.project_guid"
            raise ValueError(msg)
    return guid


def _validate_interfaces(interfaces: Mapping[str, Sequence[str]]) -> None:
    for name, addresses in interfaces.items():
        valid_addresses = isinstance(addresses, Sequence) and not isinstance(
            addresses, str
        )
        if not isinstance(name, str) or not valid_addresses:
            msg = "interface resolver must return string interface and address lists"
            raise TypeError(msg)
        if any(not isinstance(address, str) for address in addresses):
            msg = "interface resolver addresses must be strings"
            raise TypeError(msg)


def _interface_address(
    interfaces: Mapping[str, Sequence[str]], device_name: str, interface: str
) -> str:
    if not isinstance(interfaces, Mapping):
        msg = "interface resolver must return a mapping of interface address lists"
        raise TypeError(msg)
    _validate_interfaces(interfaces)
    for candidate in interface.split(","):
        addresses = interfaces.get(candidate)
        if addresses and addresses[0]:
            return addresses[0]
    msg = f'interface "{interface}" not found on device "{device_name}"'
    raise ValueError(msg)


@cache
def _fallback_ansible_temp() -> TemporaryDirectory[str]:
    """Keep Ansible's generated local temp directory alive for this process."""
    return TemporaryDirectory(prefix="sdk-ansible-")


@contextmanager
def _ansible_local_temp() -> Iterator[None]:
    """Supply a writable default only while Ansible initializes."""
    if "ANSIBLE_LOCAL_TEMP" in os.environ:
        yield
        return
    fallback = _fallback_ansible_temp().name
    os.environ["ANSIBLE_LOCAL_TEMP"] = fallback
    try:
        yield
    finally:
        if os.environ.get("ANSIBLE_LOCAL_TEMP") == fallback:
            os.environ.pop("ANSIBLE_LOCAL_TEMP", None)


def _register_ansible(environment: ImmutableSandboxedEnvironment) -> None:
    with _ansible_local_temp():
        _load_ansible_filters(environment)


def _load_ansible_filters(environment: ImmutableSandboxedEnvironment) -> None:
    # Lazy loading keeps non-rendering SDK imports independent of Ansible.
    # ruff: noqa: PLC0415
    from ansible.plugins.filter.core import FilterModule as CoreFilterModule
    from ansible.plugins.filter.encryption import FilterModule as EncryptionFilterModule
    from ansible.plugins.filter.mathstuff import FilterModule as MathFilterModule
    from ansible.plugins.filter.urls import FilterModule as URLFilterModule
    from ansible.plugins.filter.urlsplit import FilterModule as URLSplitFilterModule

    for module in (
        CoreFilterModule,
        URLFilterModule,
        URLSplitFilterModule,
        MathFilterModule,
        EncryptionFilterModule,
    ):
        for name, function in module().filters().items():
            if name not in {"default", "d"}:
                environment.filters[name] = function


def create_environment(
    *,
    scope: ResourceScope,
    rio: Mapping[str, Any],
    interface_resolver: DeviceInterfaceResolver | None,
) -> ImmutableSandboxedEnvironment:
    """Build one strict, sandboxed environment with the CLI filter names."""
    environment = ImmutableSandboxedEnvironment(
        undefined=StrictUndefined, autoescape=False
    )

    @pass_context
    def get_intf_ip(_context: Context, device_name: str, interface: str) -> str:
        guid = _project_guid(scope, rio)
        if interface_resolver is None:
            msg = "get_intf_ip requires ManifestSource.interface_resolver"
            raise ValueError(msg)
        if not isinstance(device_name, str) or not isinstance(interface, str):
            msg = "get_intf_ip requires string device_name and interface"
            raise TypeError(msg)
        return _interface_address(
            interface_resolver(guid, device_name), device_name, interface
        )

    environment.filters["getenv"] = lambda default, env_var: os.getenv(env_var, default)
    environment.filters["get_intf_ip"] = get_intf_ip
    _register_ansible(environment)
    return environment
