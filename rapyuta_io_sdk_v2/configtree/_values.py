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

"""Encode logical values and validate exact stored key payloads."""

import base64
import binascii
import hashlib
import json
import math
from datetime import date, datetime

from pydantic import ValidationError

from rapyuta_io_sdk_v2.configtree.exceptions import (
    ConfigTreeMergeConflictError,
    InputReason,
    input_error,
)
from rapyuta_io_sdk_v2.models.configtree import ConfigValue, ConfigValues


def normalize(value: object, *, seen: set[int] | None = None) -> object:
    """Convert supported logical content to JSON-safe values without cycles."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return _finite_float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return _normalize_collection(value, seen=seen)
    raise input_error(InputReason.UNSUPPORTED_CONFIGURATION_VALUE_TYPE)


def _finite_float(value: float) -> float:
    if not math.isfinite(value):
        raise input_error(InputReason.NON_FINITE_CONFIGURATION_VALUE)
    return value


def _normalize_collection(
    value: dict[object, object] | list[object], *, seen: set[int] | None
) -> object:
    seen = set() if seen is None else seen
    if id(value) in seen:
        raise input_error(InputReason.CYCLIC_CONFIGURATION_VALUE)
    seen.add(id(value))
    try:
        if isinstance(value, list):
            return [normalize(item, seen=seen) for item in value]
        if not all(isinstance(key, str) for key in value):
            raise input_error(InputReason.CONFIGURATION_MAPPING_KEYS_MUST_BE_STRINGS)
        return {key: normalize(item, seen=seen) for key, item in value.items()}
    finally:
        seen.remove(id(value))


def validate_key(key: str) -> None:
    """Require a nonambiguous slash-separated key name."""
    if not isinstance(key, str) or not _valid_key_text(key):
        raise input_error(InputReason.INVALID_CONFIGURATION_KEY_PATH, key=str(key))


def _valid_key_text(key: str) -> bool:
    if (
        not key
        or key != key.strip()
        or not all(part.strip() for part in key.split("/"))
    ):
        return False
    try:
        key.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def encode_value(
    value: object, *, metadata: dict[str, str] | None = None
) -> ConfigValue:
    """Encode a logical leaf as a typed key-value artifact."""
    normalized = normalize(value)
    if metadata is not None and (
        not isinstance(metadata, dict)
        or any(
            not isinstance(k, str) or not isinstance(v, str)
            for k, v in metadata.items()
        )
    ):
        raise input_error(InputReason.INVALID_CONFIGURATION_KEY_METADATA)
    content = (
        normalized
        if isinstance(normalized, str)
        else json.dumps(normalized, ensure_ascii=False, allow_nan=False)
    )
    raw = content.encode("utf-8")
    fields = {
        "permissions": "644",
        "content_type": "kv",
        "content_length": len(raw),
        "checksum": hashlib.md5(raw, usedforsecurity=False).hexdigest(),
        "data": base64.b64encode(raw).decode("ascii"),
    }
    if metadata is not None:
        fields["metadata"] = metadata.copy()
    return ConfigValue.model_validate(fields)


def snapshot_values(values: dict[str, ConfigValue]) -> ConfigValues:
    """Revalidate an independent plain-field snapshot of mutable entries."""
    snapshot: dict[str, ConfigValue] = {}
    for key, entry in list(values.items()):
        validate_key(key)
        if not isinstance(entry, ConfigValue):
            raise input_error(InputReason.INVALID_CONFIGURATION_KEY_PAYLOAD, key=key)
        try:
            snapshot[key] = _validated_entry(entry)
        except (ValidationError, ValueError, TypeError, binascii.Error) as error:
            raise input_error(
                InputReason.INVALID_STORED_CONFIGURATION_KEY, key=key
            ) from error
    return ConfigValues(snapshot)


def _validated_entry(entry: ConfigValue) -> ConfigValue:
    plain = entry.model_dump(exclude_unset=True, by_alias=True, warnings=False)
    strict = ConfigValue.model_validate(plain, strict=True)
    if strict.content_type != "kv" or strict.data is None or strict.checksum is None:
        raise ValueError
    raw = base64.b64decode(strict.data, validate=True)
    if strict.content_length is None or strict.content_length != len(raw):
        raise ValueError
    if strict.checksum != hashlib.md5(raw, usedforsecurity=False).hexdigest():
        raise ValueError
    return strict


def merge_values(
    destination: dict[str, ConfigValue], source: dict[str, ConfigValue]
) -> dict[str, ConfigValue]:
    """Validate source lengths, then union compatible stored entries."""
    for key, entry in source.items():
        _validate_source_length(key, entry)
    snapshot_values(source)
    snapshot_values(destination)
    conflicts = [
        key
        for key in source.keys() & destination.keys()
        if source[key].data != destination[key].data
        or ("metadata" in source[key].model_fields_set)
        != ("metadata" in destination[key].model_fields_set)
        or source[key].metadata != destination[key].metadata
    ]
    if conflicts:
        raise ConfigTreeMergeConflictError(conflicts)
    return {
        **{key: entry.model_copy(deep=True) for key, entry in destination.items()},
        **{
            key: entry.model_copy(deep=True)
            for key, entry in source.items()
            if key not in destination
        },
    }


def _validate_source_length(key: str, entry: ConfigValue) -> None:
    if not isinstance(entry, ConfigValue) or entry.data is None:
        raise input_error(InputReason.SOURCE_KEY_HAS_INVALID_CONTENT_LENGTH, key=key)
    try:
        actual = len(base64.b64decode(entry.data, validate=True))
    except (ValueError, TypeError, binascii.Error) as error:
        raise input_error(
            InputReason.SOURCE_KEY_HAS_INVALID_CONTENT_LENGTH, key=key
        ) from error
    if entry.content_length is None or entry.content_length != actual:
        raise input_error(InputReason.SOURCE_KEY_HAS_INVALID_CONTENT_LENGTH, key=key)
