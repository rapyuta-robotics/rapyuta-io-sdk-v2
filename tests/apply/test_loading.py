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
import subprocess
from pathlib import Path

import pytest

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
