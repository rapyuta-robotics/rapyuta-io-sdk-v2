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

"""Local manifest preparation and value rendering contract tests."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from rapyuta_io_sdk_v2 import ApplierOptions, ResourceScope
from rapyuta_io_sdk_v2.apply import _filters
from rapyuta_io_sdk_v2.apply._loader import prepare_source
from rapyuta_io_sdk_v2.apply.applier import Applier, AsyncApplier
from rapyuta_io_sdk_v2.apply.errors import ApplierValidationError
from rapyuta_io_sdk_v2.apply.source import ManifestSource
from rapyuta_io_sdk_v2.async_client import AsyncClient
from rapyuta_io_sdk_v2.client import Client
from rapyuta_io_sdk_v2.models.package import Package
from rapyuta_io_sdk_v2.models.role import Role
from rapyuta_io_sdk_v2.models.rolebinding import (
    RoleBinding,
    RoleBindingSpec,
    RoleRef,
)
from rapyuta_io_sdk_v2.models.utils import Domain, Subject


def _role(name: str) -> Role:
    return Role.model_validate(
        {
            "kind": "Role",
            "metadata": {"name": name},
            "spec": {"description": "fixture", "rules": []},
        }
    )


def test_files_and_resource_instances_can_be_combined(tmp_path: Path) -> None:
    manifest = tmp_path / "role.yaml"
    manifest.write_text(
        "kind: Role\nmetadata:\n  name: from-file\nspec:\n  rules: []\n"
    )

    prepared = prepare_source(
        ManifestSource(files=(manifest,), resources=(_role("from-instance"),))
    )

    assert [item.resource.metadata.name for item in prepared.resources] == [
        "from-file",
        "from-instance",
    ]
    assert prepared.resources[0].source.path == str(manifest)
    assert prepared.resources[1].source.instance_index == 0


def test_yaml_documents_json_resource_and_empty_documents(tmp_path: Path) -> None:
    yaml_file = tmp_path / "roles.yaml"
    yaml_file.write_text(
        "kind: Role\nmetadata:\n  name: first\nspec:\n  rules: []\n"
        "---\n\n---\nkind: Role\nmetadata:\n  name: second\nspec:\n  rules: []\n"
    )
    json_file = tmp_path / "third.json"
    json_file.write_text(
        '{"kind":"Role","metadata":{"name":"third"},"spec":{"rules":[]}}'
    )

    prepared = prepare_source(ManifestSource(files=(yaml_file, json_file)))

    assert [item.resource.metadata.name for item in prepared.resources] == [
        "first",
        "second",
        "third",
    ]
    assert [item.source.document_index for item in prepared.resources] == [0, 2, 0]


def test_empty_input_and_empty_yaml_documents_are_valid(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("---\n\n---\n")

    assert prepare_source(ManifestSource()).resources == ()
    assert prepare_source(ManifestSource(files=(empty_file,))).resources == ()


@pytest.mark.parametrize(
    ("contents", "category"),
    [
        ("metadata: {}", "kind"),
        ("kind: UnknownThing\nmetadata:\n  name: x", "kind"),
        ("kind: Package\nmetadata:\n  name: x\nspec: {}", "model"),
    ],
)
def test_invalid_kind_or_package_version_has_source_context(
    tmp_path: Path, contents: str, category: str
) -> None:
    manifest = tmp_path / "invalid.yaml"
    manifest.write_text(contents)

    with pytest.raises(ApplierValidationError) as error:
        prepare_source(ManifestSource(files=(manifest,)))

    assert error.value.source is not None
    assert error.value.source.path == str(manifest)
    assert error.value.category == category


def test_values_merge_in_order_and_reserved_namespaces_are_explicit(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "rendered.yaml"
    manifest.write_text(
        "kind: Role\n"
        "metadata:\n"
        "  name: '{{ name }}-{{ rio.org }}-{{ secrets.token }}'\n"
        "  labels:\n"
        "    from: '{{ nested.first }}{{ nested.second }}'\n"
        "spec:\n"
        "  rules: []\n"
    )
    prepared = prepare_source(
        ManifestSource(
            files=(manifest,),
            values=(
                {"name": "rendered", "nested": {"first": "A"}, "rio": {"org": "bad"}},
                {"nested": {"second": "B"}, "secrets": {"token": "bad"}},
            ),
            secrets=({"token": "secret-value"},),
            rio={"org": "selected"},
        )
    )

    model = prepared.resources[0].resource
    assert model.metadata.name == "rendered-selected-secret-value"
    assert model.metadata.labels == {"from": "AB"}


def test_value_mapping_requires_one_string_keyed_mapping(tmp_path: Path) -> None:
    values = tmp_path / "values.json"
    values.write_text('[{"name":"bad"}]')

    with pytest.raises(ApplierValidationError) as error:
        prepare_source(ManifestSource(values=(values,)))

    assert error.value.source is not None
    assert error.value.category == "values"


def test_missing_template_value_is_strict_and_source_aware(tmp_path: Path) -> None:
    manifest = tmp_path / "missing.yaml"
    manifest.write_text(
        "kind: Role\nmetadata:\n  name: '{{ absent }}'\nspec:\n  rules: []\n"
    )

    with pytest.raises(ApplierValidationError) as error:
        prepare_source(ManifestSource(files=(manifest,)))

    assert error.value.source is not None
    assert error.value.source.path == str(manifest)
    assert error.value.category == "template"


def test_source_construction_snapshots_iterables_and_mappings() -> None:
    original_values = {"nested": {"value": "before"}}
    value_sources = [original_values]
    resources = [_role("kept")]
    source = ManifestSource(values=value_sources, resources=resources)
    value_sources.append({"later": True})
    original_values["nested"]["value"] = "after"
    resources.clear()

    assert len(source.values) == 1
    assert source.values[0]["nested"]["value"] == "before"
    assert len(source.resources) == 1


def test_duplicate_resource_errors_retain_source_context(tmp_path: Path) -> None:
    manifest = tmp_path / "duplicate.yaml"
    manifest.write_text(
        "kind: Role\nmetadata:\n  name: repeated\nspec:\n  rules: []\n"
        "---\nkind: Role\nmetadata:\n  name: repeated\nspec:\n  rules: []\n"
    )

    with pytest.raises(ApplierValidationError) as error:
        prepare_source(ManifestSource(files=(manifest,)))

    assert error.value.category in {"ambiguous_alias", "duplicate_identity"}
    assert error.value.source is not None
    assert error.value.source.path == str(manifest)


def test_preparation_does_not_construct_clients_or_run_sops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected(*_args: object, **_kwargs: object) -> None:
        message = "offline preparation attempted external work"
        raise AssertionError(message)

    monkeypatch.setattr(subprocess, "run", unexpected)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", unexpected)
    monkeypatch.setattr(Client, "__init__", unexpected)
    monkeypatch.setattr(AsyncClient, "__init__", unexpected)
    prepared = prepare_source(ManifestSource(resources=(_role("offline"),)))

    assert len(prepared.resources) == 1
    assert prepared.dependency_graph.edges == ()


def test_preparing_resource_instances_preserves_caller_state() -> None:
    resource = _role("unchanged")
    before = resource.model_dump(exclude_unset=True)
    before_fields = set(resource.model_fields_set)

    prepared = prepare_source(ManifestSource(resources=(resource,)))

    assert resource.model_dump(exclude_unset=True) == before
    assert resource.model_fields_set == before_fields
    assert prepared.resources[0].resource is not resource
    assert prepared.resources[0].resource.model_fields_set == before_fields


@pytest.mark.parametrize("facade", [Applier, AsyncApplier])
def test_package_instance_preserves_normalized_command_like_file_input(
    tmp_path: Path, facade: type
) -> None:
    data = {
        "kind": "Package",
        "metadata": {"name": "bash-package", "version": "v1"},
        "spec": {"executables": [{"command": "echo hello", "runAsBash": True}]},
    }
    manifest = tmp_path / "package.json"
    manifest.write_text(json.dumps(data))
    package = Package.model_validate(data)
    before = package.model_dump(exclude_unset=True)
    expected = ["/bin/bash", "-c", "echo hello"]
    assert package.spec.executables[0].command == expected

    applier = facade(ManifestSource(resources=(package,)))
    prepared = applier.inspect().resolved_manifests[0]
    from_file = (
        facade(ManifestSource(files=(manifest,))).inspect().resolved_manifests[0]
    )

    assert prepared.spec.executables[0].command == expected
    assert prepared.model_dump(exclude_unset=True) == before
    assert prepared.model_dump() == from_file.model_dump()
    assert prepared.spec.executables[0].model_fields_set == (
        package.spec.executables[0].model_fields_set
    )
    prepared.spec.executables[0].command.append("changed")
    assert (
        applier.inspect().resolved_manifests[0].spec.executables[0].command == expected
    )
    assert package.model_dump(exclude_unset=True) == before


@pytest.mark.parametrize("missing_kind", ["subject", "domain"])
def test_rolebinding_file_missing_reference_kind_has_source_context(
    tmp_path: Path, missing_kind: str
) -> None:
    manifest = tmp_path / "binding.yaml"
    subject_kind = "" if missing_kind == "subject" else "kind: User\n    "
    domain_kind = "" if missing_kind == "domain" else "kind: Project\n    "
    manifest.write_text(
        "kind: RoleBinding\n"
        "metadata: {}\n"
        "spec:\n"
        "  roleRef:\n"
        "    name: viewer\n"
        "  domain:\n"
        f"    {domain_kind}name: alpha\n"
        "  subject:\n"
        f"    {subject_kind}name: ava\n"
    )

    with pytest.raises(ApplierValidationError) as error:
        prepare_source(ManifestSource(files=(manifest,)))

    assert error.value.source is not None
    assert error.value.source.path == str(manifest)
    assert error.value.category == "identity"


@pytest.mark.parametrize("missing_kind", ["subject", "domain"])
def test_rolebinding_instance_missing_reference_kind_has_source_context(
    missing_kind: str,
) -> None:
    binding = RoleBinding(
        metadata={},
        spec=RoleBindingSpec(
            roleRef=RoleRef(name="viewer"),
            domain=Domain(
                name="alpha", kind=None if missing_kind == "domain" else "Project"
            ),
            subject=Subject(
                name="ava", kind=None if missing_kind == "subject" else "User"
            ),
        ),
    )

    with pytest.raises(ApplierValidationError) as error:
        prepare_source(ManifestSource(resources=(binding,)))

    assert error.value.source is not None
    assert error.value.source.instance_index == 0
    assert error.value.category == "identity"


def _filter_manifest(path: Path, expression: str) -> Path:
    path.write_text(
        "kind: Role\nmetadata:\n  name: filter-test\nspec:\n"
        f'  description: "{{{{ {expression} }}}}"\n  rules: []\n'
    )
    return path


@pytest.mark.parametrize("facade", [Applier, AsyncApplier])
def test_interface_resolver_only_runs_for_evaluated_filter(
    tmp_path: Path, facade: type, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected(*_args: object, **_kwargs: object) -> None:
        msg = "offline rendering attempted platform access"
        raise AssertionError(msg)

    monkeypatch.setattr(Client, "__init__", unexpected)
    monkeypatch.setattr(AsyncClient, "__init__", unexpected)
    plain = _filter_manifest(tmp_path / "plain.yaml", "'plain'")
    called: list[tuple[str, str]] = []

    def resolve(project: str, device: str) -> dict[str, list[str]]:
        called.append((project, device))
        return {"eth0": ["10.1.1.1", "10.1.1.2"]}

    source = ManifestSource(files=(plain,), interface_resolver=resolve)
    facade(source).inspect()
    assert called == []
    filtered = _filter_manifest(
        tmp_path / "filtered.yaml", "'edge' | get_intf_ip('eth0')"
    )
    source = ManifestSource(files=(filtered,), interface_resolver=resolve)
    options = ApplierOptions(scope=ResourceScope(project_guid="project-fixture"))
    result = facade(source, options).inspect()
    assert result.rendered_documents[0].data["spec"]["description"] == "10.1.1.1"
    assert called == [("project-fixture", "edge")]


@pytest.mark.parametrize("facade", [Applier, AsyncApplier])
def test_skipped_device_branch_does_not_resolve(tmp_path: Path, facade: type) -> None:
    manifest = tmp_path / "conditional.yaml"
    manifest.write_text(
        "kind: Role\nmetadata:\n  name: conditional\nspec:\n"
        "  description: \"{% if use_device %}{{ 'edge' | get_intf_ip('eth0') }}"
        '{% else %}plain{% endif %}"\n  rules: []\n'
    )
    calls: list[tuple[str, str]] = []

    def resolve(project: str, device: str) -> dict[str, list[str]]:
        calls.append((project, device))
        return {"eth0": ["192.0.2.1"]}

    options = ApplierOptions(scope=ResourceScope(project_guid="project-fixture"))
    skipped = facade(
        ManifestSource(
            files=(manifest,),
            values=({"use_device": False},),
            interface_resolver=resolve,
        ),
        options,
    ).inspect()
    assert skipped.rendered_documents[0].data["spec"]["description"] == "plain"
    assert calls == []

    selected = facade(
        ManifestSource(
            files=(manifest,),
            values=({"use_device": True},),
            interface_resolver=resolve,
        ),
        options,
    ).inspect()
    assert selected.rendered_documents[0].data["spec"]["description"] == "192.0.2.1"
    assert calls == [("project-fixture", "edge")]


@pytest.mark.parametrize("facade", [Applier, AsyncApplier])
def test_jinja_d_alias_keeps_undefined_fallback(tmp_path: Path, facade: type) -> None:
    manifest = _filter_manifest(
        tmp_path / "alias.yaml", "missing_value | d('fallback')"
    )
    result = facade(ManifestSource(files=(manifest,))).inspect()
    assert result.rendered_documents[0].data["spec"]["description"] == "fallback"


@pytest.mark.parametrize("configured", [False, True])
def test_ansible_filters_render_with_unwritable_home(
    tmp_path: Path, *, configured: bool
) -> None:
    blocked_home = tmp_path / "blocked-home"
    blocked_home.write_text("not a directory")
    manifest = _filter_manifest(tmp_path / "plain.yaml", "'plain'")
    environment = os.environ.copy()
    environment.pop("ANSIBLE_LOCAL_TEMP", None)
    environment["HOME"] = str(blocked_home)
    if configured:
        environment["ANSIBLE_LOCAL_TEMP"] = str(tmp_path / "caller-ansible-temp")
    script = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "from rapyuta_io_sdk_v2 import Applier, ManifestSource\n"
        "result = Applier(ManifestSource(files=(Path(sys.argv[1]),))).inspect()\n"
        "from ansible import constants as C\n"
        "assert result.rendered_documents[0].data['spec']['description'] == 'plain'\n"
        "configured = sys.argv[2] == 'True'\n"
        "if configured:\n"
        "    assert Path(C.DEFAULT_LOCAL_TMP).is_relative_to("
        "os.environ['ANSIBLE_LOCAL_TEMP'])\n"
        "else:\n"
        "    assert 'ANSIBLE_LOCAL_TEMP' not in os.environ\n"
    )
    result = subprocess.run(  # noqa: S603 - isolated SDK import probe
        [sys.executable, "-c", script, str(manifest), str(configured)],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "failure",
    [
        (ResourceScope(), lambda _p, _d: {}, None, "scope.project_guid"),
        (ResourceScope(project_guid="one"), None, None, "interface_resolver"),
        (
            ResourceScope(project_guid="one"),
            lambda _p, _d: {},
            {"project": {"guid": "two"}},
            "rio.project.guid",
        ),
        (
            ResourceScope(project_guid="one"),
            lambda _p, _d: {"eth0": []},
            None,
            'interface "eth0" not found on device "edge"',
        ),
        (
            ResourceScope(project_guid="one"),
            lambda _p, _d: {"eth0": "bad"},
            None,
            "address lists",
        ),
    ],
)
def test_interface_failures_are_source_aware(
    tmp_path: Path,
    failure: tuple[ResourceScope, object, dict | None, str],
) -> None:
    scope, resolver, rio, message = failure
    manifest = _filter_manifest(
        tmp_path / "filtered.yaml", "'edge' | get_intf_ip('eth0')"
    )
    source = ManifestSource(files=(manifest,), rio=rio, interface_resolver=resolver)
    with pytest.raises(ApplierValidationError) as error:
        Applier(source, ApplierOptions(scope=scope))
    assert error.value.category == "template"
    assert error.value.source.path == str(manifest)
    assert message in str(error.value)


@pytest.mark.parametrize("reason", ["lookup failed", "device not ready"])
def test_resolver_failures_keep_manifest_source(tmp_path: Path, reason: str) -> None:
    manifest = _filter_manifest(
        tmp_path / "device.yaml", "'edge' | get_intf_ip('eth0')"
    )

    def fail(_project: str, _device: str) -> dict[str, list[str]]:
        raise RuntimeError(reason)

    source = ManifestSource(files=(manifest,), interface_resolver=fail)
    options = ApplierOptions(scope=ResourceScope(project_guid="project-fixture"))
    with pytest.raises(ApplierValidationError) as error:
        Applier(source, options)
    assert error.value.category == "template"
    assert error.value.source.path == str(manifest)
    assert reason in str(error.value)


def test_no_address_matches_cli_reference_identifiers(tmp_path: Path) -> None:
    records = json.loads(
        (Path(__file__).parent / "fixtures/parity/rio-filters/errors.json").read_text()
    )
    reference = next(item for item in records if item["id"] == "interface-no-address")
    manifest = _filter_manifest(
        tmp_path / "device.yaml", "'edge-test' | get_intf_ip('eth0,tailscale0')"
    )
    source = ManifestSource(
        files=(manifest,),
        interface_resolver=lambda _p, _d: {"eth0": [], "tailscale0": [""]},
    )
    options = ApplierOptions(scope=ResourceScope(project_guid="project-fixture"))
    with pytest.raises(ApplierValidationError) as error:
        Applier(source, options)
    assert error.value.source.path == str(manifest)
    assert error.value.category == "template"
    for identifier in ("edge-test", "eth0,tailscale0"):
        assert identifier in reference["message"]
        assert identifier in str(error.value)


@pytest.mark.parametrize(
    "expression",
    ["'x' | unknown_filter", "1 | log(0, 2)", "'fallback' | getenv(42)"],
)
def test_filter_errors_prevent_resource_operations(
    tmp_path: Path, expression: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _filter_manifest(tmp_path / "invalid.yaml", expression)

    def unexpected(*_args: object, **_kwargs: object) -> None:
        msg = "resource operation began during rendering"
        raise AssertionError(msg)

    monkeypatch.setattr(Client, "__init__", unexpected)
    monkeypatch.setattr(AsyncClient, "__init__", unexpected)
    with pytest.raises(ApplierValidationError) as error:
        Applier(ManifestSource(files=(manifest,)))
    assert error.value.category == "template"
    assert error.value.source.path == str(manifest)


def test_ansible_initialization_failure_is_source_aware(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _filter_manifest(tmp_path / "filter.yaml", "'x'")

    def fail(_environment: object) -> None:
        msg = "Ansible filter import failed"
        raise ImportError(msg)

    monkeypatch.setattr(_filters, "_register_ansible", fail)
    with pytest.raises(ApplierValidationError) as error:
        Applier(ManifestSource(files=(manifest,)))
    assert error.value.category == "template"
    assert error.value.source.path == str(manifest)
    assert "Ansible filter import failed" in str(error.value)


@pytest.mark.parametrize("facade", [Applier, AsyncApplier])
def test_rendered_documents_are_ordered_and_independent(
    tmp_path: Path, facade: type
) -> None:
    first = tmp_path / "first.yaml"
    first.write_text(
        "kind: Role\nmetadata:\n  name: first\nspec:\n  rules: []\n"
        "---\n\n---\nkind: Role\nmetadata:\n  name: second\nspec:\n  rules: []\n"
    )
    second = _filter_manifest(tmp_path / "second.yaml", "'third'")
    instance = _role("instance")
    inspector = facade(ManifestSource(files=(first, second), resources=(instance,)))
    documents = inspector.inspect().rendered_documents
    assert [item.data["metadata"]["name"] for item in documents] == [
        "first",
        "second",
        "filter-test",
        "instance",
    ]
    assert [item.source.document_index for item in documents[:3]] == [0, 2, 0]
    assert [item.source.path for item in documents[:3]] == [
        str(first),
        str(first),
        str(second),
    ]
    assert documents[3].source.instance_index == 0
    assert len(inspector.inspect().resolved_manifests) == len(documents)
    documents[0].data["metadata"]["name"] = "changed"
    assert inspector.inspect().rendered_documents[0].data["metadata"]["name"] == "first"
