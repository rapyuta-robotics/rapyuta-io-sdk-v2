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

"""Pure validation of named documents, stored values, and refspecs."""

import base64
import hashlib
import json
import traceback
from pathlib import Path

import pytest

from rapyuta_io_sdk_v2.configtree import (
    ConfigTreeInputError,
    ConfigTreeMergeConflictError,
    ConfigTreeReferenceError,
    parse_refspec,
)
from rapyuta_io_sdk_v2.configtree._documents import prepare_documents
from rapyuta_io_sdk_v2.configtree._values import (
    encode_value,
    merge_values,
    snapshot_values,
)


@pytest.mark.parametrize("scope", ["org", "proj"])
@pytest.mark.parametrize("selector", ["", "/rev-123", "/release"])
def test_refspec_forms(scope: str, selector: str) -> None:
    ref = parse_refspec(f"{scope}/source{selector}")
    assert ref.is_org is (scope == "org")
    assert ref.revision_id == ("rev-123" if selector == "/rev-123" else None)
    assert ref.milestone == ("release" if selector == "/release" else None)


@pytest.mark.parametrize("ref", ["", "org/", "bad/tree", "org/tree/", "org/tree/a/b"])
def test_invalid_refspec(ref: str) -> None:
    with pytest.raises(ConfigTreeReferenceError):
        parse_refspec(ref)


def test_document_mix_and_exact_metadata(tmp_path: Path) -> None:
    robot = tmp_path / "robot.json"
    robot.write_text(
        '{"speed":{"value":2,"metadata":{"unit":"m/s"}},'
        '"empty":{"value":false,"metadata":{}},"list":[1,2]}'
    )
    site = tmp_path / "site.yaml"
    site.write_text("name: 東京\nempty: {}\n")
    extra = tmp_path / "extra.yml"
    extra.write_text("date: 2026-10-13\n")
    values = prepare_documents([robot, site, extra])
    assert set(values) == {
        "robot/speed",
        "robot/empty",
        "robot/list",
        "site/name",
        "site/empty",
        "extra/date",
    }
    assert values["robot/speed"].metadata == {"unit": "m/s"}
    assert values["robot/empty"].metadata == {}
    assert "metadata" in values["robot/empty"].model_fields_set
    assert base64.b64decode(values["site/name"].data).decode() == "東京"
    unicode_byte_length = len("東京".encode())
    assert values["site/name"].content_length == unicode_byte_length
    assert base64.b64decode(values["extra/date"].data).decode() == "2026-10-13"


def test_duplicate_keys_fail_without_values(tmp_path: Path) -> None:
    path = tmp_path / "secret.json"
    path.write_text('{"password":"sensitive","password":"different"}')
    with pytest.raises(ConfigTreeInputError) as captured:
        prepare_documents([path])
    assert "sensitive" not in str(captured.value)
    assert captured.value.file_path == str(path)


def test_yaml_merge_preserves_explicit_and_sequence_precedence(tmp_path: Path) -> None:
    path = tmp_path / "robot.yaml"
    path.write_text(
        "first: &first\n  speed: 1\n  choice: first\n"
        "second: &second\n  speed: 3\n  choice: second\n"
        "settings:\n  <<: [*first, *second]\n  speed: 2\n"
    )

    values = prepare_documents([path])

    assert values["robot/settings/speed"].data == encode_value(2).data
    assert values["robot/settings/choice"].data == encode_value("first").data


def test_yaml_merge_still_rejects_duplicate_explicit_keys(tmp_path: Path) -> None:
    path = tmp_path / "robot.yaml"
    path.write_text(
        "defaults: &defaults\n  speed: 1\n"
        "settings:\n  <<: *defaults\n  speed: 2\n  speed: 3\n"
    )

    with pytest.raises(ConfigTreeInputError) as captured:
        prepare_documents([path])
    assert captured.value.file_path == str(path)
    assert captured.value.key == "speed"


def test_yaml_merge_rejects_duplicates_inside_inline_source(tmp_path: Path) -> None:
    path = tmp_path / "robot.yaml"
    path.write_text("settings:\n  <<: {speed: 1, speed: 2}\n")

    with pytest.raises(ConfigTreeInputError) as captured:
        prepare_documents([path])

    assert captured.value.file_path == str(path)
    assert captured.value.key == "speed"


def test_yaml_nested_merge_keeps_final_override(tmp_path: Path) -> None:
    path = tmp_path / "robot.yaml"
    path.write_text(
        "base: &base {speed: 1, label: base}\n"
        "middle: &middle {<<: *base, speed: 2}\n"
        "settings: {<<: *middle, speed: 3}\n"
    )

    values = prepare_documents([path])

    assert values["robot/settings/speed"].data == encode_value(3).data
    assert values["robot/settings/label"].data == encode_value("base").data


def test_import_rejects_surrogate_path_components(tmp_path: Path) -> None:
    path = tmp_path / "robot.json"
    path.write_text(json.dumps({chr(0xD800): 1, chr(0xD801): 2}))

    with pytest.raises(ConfigTreeInputError) as captured:
        prepare_documents([path])

    assert captured.value.file_path == str(path)
    assert captured.value.key == chr(0xD800)


def test_snapshot_rejects_mutated_checksum_and_merge_conflicts() -> None:
    first = encode_value("東京", metadata={})
    assert first.content_length == len("東京".encode())
    second = encode_value("東京")
    with pytest.raises(ConfigTreeMergeConflictError) as captured:
        merge_values({"a": first}, {"a": second})
    assert captured.value.conflicting_keys == ["a"]
    first.checksum = "bad"
    with pytest.raises(ConfigTreeInputError) as captured:
        snapshot_values({"a": first})
    assert captured.value.key == "a"


@pytest.mark.parametrize(
    "content",
    [
        "",
        "{}",
        '{"a/b":1}',
        '{"a":1,"a/b":2}',
        '{"a":{"value":1,"metadata":{"unit":2}}}',
        '{"a":NaN}',
        '{"a":{"value":1,"value":2}}',
    ],
)
def test_invalid_json_document_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "robot.json"
    path.write_text(content)
    with pytest.raises(ConfigTreeInputError) as captured:
        prepare_documents([path])
    assert captured.value.file_path == str(path)
    if content:
        assert content not in str(captured.value)


@pytest.mark.parametrize(
    "content",
    ["a: 1\na: 2\n", "a: !!python/object/apply:os.system ['true']\n", "a: &a [*a]\n"],
)
def test_invalid_yaml_document_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "robot.yaml"
    path.write_text(content)
    with pytest.raises(ConfigTreeInputError) as captured:
        prepare_documents([path])
    assert captured.value.file_path == str(path)


@pytest.mark.parametrize(
    ("suffix", "content"),
    [
        ("json", '{"password": "very_secret", bad}'),
        ("yaml", "password: very_secret: extra\n"),
    ],
)
def test_parser_error_reports_safe_location(
    tmp_path: Path, suffix: str, content: str
) -> None:
    path = tmp_path / f"robot.{suffix}"
    path.write_text(content)
    with pytest.raises(ConfigTreeInputError) as captured:
        prepare_documents([path])
    error = captured.value
    assert error.file_path == str(path)
    assert error.line == 1
    assert isinstance(error.column, int)
    assert error.column > 0
    assert error.__cause__ is None
    assert "very_secret" not in str(error)
    assert "very_secret" not in "".join(traceback.format_exception(error))


def test_import_accepts_spaces_inside_valid_prefixed_paths(tmp_path: Path) -> None:
    path = tmp_path / "robot.json"
    path.write_text(
        '{" section ":{"speed":2}," leading":{"value":3,"metadata":{"unit":"m/s"}}}'
    )
    values = prepare_documents([path])
    assert set(values) == {"robot/ section /speed", "robot/ leading"}
    assert values["robot/ leading"].metadata == {"unit": "m/s"}


@pytest.mark.parametrize("name", ["", " ", "bad/name", "trailing "])
def test_import_rejects_invalid_prefixed_paths(tmp_path: Path, name: str) -> None:
    path = tmp_path / "robot.json"
    path.write_text("{" + f'"{name}":1' + "}")
    with pytest.raises(ConfigTreeInputError) as captured:
        prepare_documents([path])
    assert captured.value.file_path == str(path)


def test_wrapper_boundaries_do_not_leak_metadata(tmp_path: Path) -> None:
    path = tmp_path / "robot.json"
    path.write_text(
        '{"group":{"value":{"speed":2},"metadata":{"unit":"m/s"}},'
        '"list":[{"value":3,"metadata":{"unit":"m/s"}}],'
        '"ordinary":{"value":2,"metadata":null},'
        '"root_value":{"value":null,"metadata":{}}}'
    )
    values = prepare_documents([path])
    assert "robot/group/speed" in values
    assert "metadata" not in values["robot/group/speed"].model_fields_set
    assert "robot/list" in values
    assert "robot/ordinary/value" in values
    assert "robot/ordinary/metadata" in values
    assert values["robot/root_value"].metadata == {}


def test_duplicate_stems_and_bad_named_inputs(tmp_path: Path) -> None:
    one = tmp_path / "robot.json"
    two = tmp_path / "robot.yaml"
    one.write_text('{"a":1}')
    two.write_text("b: 2\n")
    with pytest.raises(ConfigTreeInputError):
        prepare_documents([one, two])
    with pytest.raises(ConfigTreeInputError):
        prepare_documents(one)
    with pytest.raises(ConfigTreeInputError):
        prepare_documents([])


@pytest.mark.parametrize(
    "field", ["data", "content_type", "checksum", "content_length"]
)
def test_snapshot_rejects_missing_required_fields(field: str) -> None:
    value = encode_value(0)
    setattr(value, field, None)
    with pytest.raises(ConfigTreeInputError) as captured:
        snapshot_values({"bad": value})
    assert captured.value.key == "bad"


def test_merge_preserves_source_payload_and_reports_all_conflicts() -> None:
    shared = encode_value("same")
    source_only = encode_value("東京", metadata={"unit": "text"})
    source_only.permissions = "600"
    source_only.url = "https://example.test/artifact"
    source = {"shared": shared, "new": source_only}
    false_value = False
    destination = {
        "shared": shared.model_copy(deep=True),
        "old": encode_value(false_value),
    }
    merged = merge_values(destination, source)
    assert set(merged) == {"shared", "new", "old"}
    assert merged["new"].model_dump(exclude_unset=True) == source_only.model_dump(
        exclude_unset=True
    )
    assert merged["new"] is not source_only
    different = {"a": encode_value(1), "b": encode_value(2)}
    with pytest.raises(ConfigTreeMergeConflictError) as captured:
        merge_values({"a": encode_value(3), "b": encode_value(4)}, different)
    assert captured.value.conflicting_keys == ["a", "b"]


def test_merge_rejects_stale_multibyte_source_without_repair() -> None:
    source = encode_value("東京")
    stale_length = 2
    source.content_length = stale_length
    checksum = hashlib.md5("東京".encode(), usedforsecurity=False).hexdigest()
    with pytest.raises(ConfigTreeInputError) as captured:
        merge_values({}, {"unicode": source})
    assert captured.value.key == "unicode"
    assert source.content_length == stale_length
    assert source.checksum == checksum


def test_merge_rejects_missing_or_shared_stale_source_length() -> None:
    missing = encode_value("same")
    missing.content_length = None
    with pytest.raises(ConfigTreeInputError) as captured:
        merge_values({"shared": encode_value("same")}, {"shared": missing})
    assert captured.value.key == "shared"
    stale = encode_value("same")
    stale.content_length = 1
    with pytest.raises(ConfigTreeInputError) as captured:
        merge_values({"shared": encode_value("same")}, {"shared": stale})
    assert captured.value.key == "shared"
    assert merge_values({}, {}) == {}


@pytest.mark.parametrize("key", ["", " bad", "a//b", "a/", "a/ ", chr(0xD800)])
def test_snapshot_rejects_malformed_key_path(key: str) -> None:
    with pytest.raises(ConfigTreeInputError) as captured:
        snapshot_values({key: encode_value("valid")})
    assert captured.value.key == key
