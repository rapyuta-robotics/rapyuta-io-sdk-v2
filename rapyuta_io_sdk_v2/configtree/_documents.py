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

"""Safe named document parsing and rio-compatible metadata splitting."""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from rapyuta_io_sdk_v2.configtree._values import encode_value, normalize, validate_key
from rapyuta_io_sdk_v2.configtree.exceptions import (
    ConfigTreeInputError,
    InputReason,
    input_error,
)
from rapyuta_io_sdk_v2.models.configtree import ConfigValue


def is_metadata_wrapper(value: object) -> bool:
    """Recognize only exact value/metadata mappings with dictionary metadata."""
    return (
        isinstance(value, dict)
        and set(value) == {"value", "metadata"}
        and isinstance(value["metadata"], dict)
    )


def split_metadata(
    data: object,
) -> tuple[object, dict[tuple[str, ...], dict[str, str]]]:
    """Remove nested wrappers and return opaque attachments at original paths."""
    attachments: dict[tuple[str, ...], dict[str, str]] = {}
    return _split_node(data, (), attachments), attachments


def _split_node(
    value: object,
    path: tuple[str, ...],
    attachments: dict[tuple[str, ...], dict[str, str]] | None,
) -> object:
    if not isinstance(value, dict):
        return value
    result = {}
    for key, child in value.items():
        child_path = (*path, key)
        if is_metadata_wrapper(child):
            _attach_metadata(child["metadata"], child_path, attachments)
            result[key] = child["value"]
        else:
            result[key] = _split_node(child, child_path, attachments)
    return result


def _attach_metadata(
    metadata: dict[object, object],
    path: tuple[str, ...],
    attachments: dict[tuple[str, ...], dict[str, str]] | None,
) -> None:
    if attachments is None:
        return
    if any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in metadata.items()
    ):
        raise input_error(
            InputReason.INVALID_CONFIGURATION_METADATA, key="/".join(path)
        )
    attachments[path] = metadata.copy()


def split_content(data: object) -> object:
    """Use the shared wrapper recognition without exposing attachments."""
    return _split_node(data, (), None)


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise input_error(InputReason.DUPLICATE_CONFIGURATION_MAPPING_KEY, key=key)
        result[key] = value
    return result


class _UniqueLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping entries."""

    def __init__(self, stream: str) -> None:
        super().__init__(stream)
        self._checked_mapping_nodes: set[int] = set()

    def flatten_mapping(self, node: yaml.MappingNode) -> None:
        """Check authored keys before YAML inserts inherited merge entries."""
        if id(node) not in self._checked_mapping_nodes:
            seen: set[object] = set()
            for key_node, _ in node.value:
                key = (
                    "<<"
                    if key_node.tag == "tag:yaml.org,2002:merge"
                    else self.construct_object(key_node, deep=True)
                )
                if key in seen:
                    raise input_error(
                        InputReason.DUPLICATE_CONFIGURATION_MAPPING_KEY, key=str(key)
                    )
                seen.add(key)
            self._checked_mapping_nodes.add(id(node))
        super().flatten_mapping(node)


def _construct_mapping(loader: _UniqueLoader, node: yaml.MappingNode) -> dict[str, Any]:
    loader.flatten_mapping(node)
    return {
        loader.construct_object(k, deep=True): loader.construct_object(v, deep=True)
        for k, v in node.value
    }


_UniqueLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def _parse(path: Path) -> dict[str, Any]:
    suffix = _supported_suffix(path)
    try:
        data = _parse_text(path.read_text(encoding="utf-8"), suffix)
        if not isinstance(data, dict) or not data:
            raise input_error(
                InputReason.CONFIGURATION_FILE_MUST_CONTAIN_A_NONEMPTY_MAPPING
            )
        normalize(data)
    except ConfigTreeInputError:
        raise
    except (
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        yaml.YAMLError,
        RecursionError,
    ) as error:
        line, column = _parser_location(error)
    else:
        return data
    # Raise after leaving the except block so a parser exception cannot expose
    # source text through its chained traceback.
    raise input_error(
        InputReason.INVALID_CONFIGURATION_DOCUMENT,
        file_path=str(path),
        line=line,
        column=column,
    )


def _supported_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        raise input_error(
            InputReason.UNSUPPORTED_CONFIGURATION_FILE_SUFFIX, file_path=str(path)
        )
    return suffix


def _parser_location(error: BaseException) -> tuple[int | None, int | None]:
    if isinstance(error, json.JSONDecodeError):
        return error.lineno, error.colno
    if isinstance(error, yaml.YAMLError):
        mark = getattr(error, "problem_mark", None)
        if mark is not None:
            return mark.line + 1, mark.column + 1
    return None, None


def _parse_text(text: str, suffix: str) -> object:
    if suffix == ".json":
        return json.loads(
            text,
            object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    # _UniqueLoader only extends SafeLoader to reject duplicate keys.
    return yaml.load(text, Loader=_UniqueLoader)  # noqa: S506


def _flatten(
    value: dict[str, Any], path: tuple[str, ...], result: dict[tuple[str, ...], Any]
) -> None:
    for name, child in value.items():
        if not isinstance(name, str) or not _valid_component(name):
            raise input_error(
                InputReason.INVALID_CONFIGURATION_PATH_COMPONENT, key=str(name)
            )
        child_path = (*path, name)
        if isinstance(child, dict) and child:
            _flatten(child, child_path, result)
        else:
            if child_path in result:
                raise input_error(
                    InputReason.AMBIGUOUS_CONFIGURATION_PATH, key="/".join(child_path)
                )
            result[child_path] = child


def _valid_component(name: str) -> bool:
    if not name.strip() or "/" in name:
        return False
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _prepare_one(path: Path, stem: str) -> dict[str, ConfigValue]:
    content, attachments = split_metadata(_parse(path))
    leaves: dict[tuple[str, ...], Any] = {}
    _flatten(content, (stem,), leaves)
    if not leaves:
        raise input_error(InputReason.CONFIGURATION_FILE_HAS_NO_KEYS)
    result: dict[str, ConfigValue] = {}
    for leaf_path, value in leaves.items():
        key = "/".join(leaf_path)
        try:
            validate_key(key)
            result[key] = encode_value(value, metadata=attachments.get(leaf_path[1:]))
        except ConfigTreeInputError as error:
            if error.key is None:
                error.key = key
            raise
    return result


def prepare_documents(files: Iterable[str | Path]) -> dict[str, ConfigValue]:
    """Parse every named file, flatten leaves, and encode typed key values."""
    result: dict[str, ConfigValue] = {}
    for path in _named_paths(files):
        try:
            result.update(_prepare_one(path, path.stem))
        except ConfigTreeInputError as error:
            if error.file_path is None:
                error.file_path = str(path)
            raise
    return result


def _named_paths(files: Iterable[str | Path]) -> list[Path]:
    if isinstance(files, (str, Path)):
        raise input_error(InputReason.FILES_MUST_BE_AN_ITERABLE_OF_NAMED_PATHS)
    paths = _materialize_paths(files)
    if not paths:
        raise input_error(InputReason.AT_LEAST_ONE_CONFIGURATION_FILE_IS_REQUIRED)
    stems: set[str] = set()
    for path in paths:
        stem = path.stem
        if not _valid_component(stem) or stem in stems:
            raise input_error(
                InputReason.DUPLICATE_OR_INVALID_CONFIGURATION_FILE_STEM,
                file_path=str(path),
            )
        stems.add(stem)
    return paths


def _materialize_paths(files: Iterable[str | Path]) -> list[Path]:
    try:
        return [Path(item) for item in files]
    except (TypeError, ValueError) as error:
        raise input_error(
            InputReason.FILES_MUST_BE_AN_ITERABLE_OF_NAMED_PATHS
        ) from error
