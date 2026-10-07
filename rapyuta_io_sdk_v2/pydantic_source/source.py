"""Optional Pydantic Settings source for ConfigTrees and local exports."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import AliasChoices, AliasPath
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.features import require_dependency

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.client import Client


def _without_metadata(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    if set(value) == {"value", "metadata"} and isinstance(value["metadata"], dict):
        return value["value"]
    return {key: _without_metadata(item) for key, item in value.items()}


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        return {prefix: value}
    result: dict[str, Any] = {}
    for key, item in value.items():
        path = f"{prefix}/{key}" if prefix else str(key)
        result.update(_flatten(item, path))
    return result


def _nest(values: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    leaves: set[str] = set()
    for path, value in values.items():
        parts = path.split("/")
        target = result
        for index, part in enumerate(parts[:-1]):
            if "/".join(parts[: index + 1]) in leaves:
                raise ValueError(f"conflicting ConfigTree paths at {path}")
            existing = target.setdefault(part, {})
            if not isinstance(existing, dict):
                raise ValueError(f"conflicting ConfigTree paths at {path}")
            target = existing
        if parts[-1] in target and isinstance(target[parts[-1]], dict):
            raise ValueError(f"conflicting ConfigTree paths at {path}")
        target[parts[-1]] = value
        leaves.add(path)
    return result


class ConfigTreeSource(PydanticBaseSettingsSource):
    """Load a ConfigTree when Pydantic invokes the source, never during import.

    An injected client remains owned by the caller. Local JSON/YAML exports
    are wrapped under the file stem, matching the ConfigTree export convention.
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        config: Configuration | None = None,
        tree_name: str = "default",
        key_prefix: str = "",
        with_project: bool = True,
        local_file: str | Path | None = None,
        *,
        client: Client | None = None,
    ):
        super().__init__(settings_cls)
        self.config = config or (client.config if client is not None else Configuration())
        self._client = client
        self._tree_name = tree_name
        self._local_file = Path(local_file) if local_file is not None else None
        self._top_prefix = key_prefix.strip("/")
        self._with_project = with_project
        self._configtree_data: dict[str, Any] | None = None

    def _load_data(self) -> dict[str, Any]:
        self.config.features.require("configtree_source")
        if self._local_file is not None:
            suffix = self._local_file.suffix.lower()
            content = self._local_file.read_text(encoding="utf-8")
            if suffix == ".json":
                value = json.loads(content)
            elif suffix in (".yaml", ".yml"):
                value = require_dependency("yaml", "configtree").safe_load(content)
            else:
                raise ValueError("unsupported local file format; use JSON or YAML")
            if not isinstance(value, dict):
                raise ValueError("local ConfigTree data must be a mapping")
            flat = _flatten({self._local_file.stem: _without_metadata(value)})
        else:
            from rapyuta_io_sdk_v2.client import Client
            from rapyuta_io_sdk_v2.context import RequestContext

            owned = self._client is None
            client = (
                self._client if self._client is not None else Client(config=self.config)
            )
            try:
                tree = client.get_configtree(
                    name=self._tree_name,
                    include_data=True,
                    content_types=["kv"],
                    key_prefixes=[self._top_prefix] if self._top_prefix else None,
                    context=RequestContext(with_project=self._with_project),
                )
                flat = {
                    key: self._decode_value(item.data)
                    for key, item in (tree.keys or {}).items()
                    if item.data is not None
                }
            finally:
                if owned:
                    client.close()
        if self._top_prefix:
            prefix = self._top_prefix + "/"
            flat = {
                key[len(prefix) :]: value
                for key, value in flat.items()
                if key.startswith(prefix)
            }
        return _nest(flat)

    @staticmethod
    def _decode_value(encoded_data: str) -> Any:
        decoded = base64.b64decode(encoded_data, validate=True).decode("utf-8")
        try:
            return json.loads(decoded)
        except ValueError:
            return decoded

    def __call__(self) -> dict[str, Any]:
        self._configtree_data = self._load_data()
        if self.settings_cls.model_config.get("extra") == "allow":
            result = dict(self._configtree_data)
        else:
            result = {}
        for field_name, field in self.settings_cls.model_fields.items():
            value, key, _ = self.get_field_value(field, field_name)
            # Explicit JSON null is a value, not a missing field.
            if (
                key in self._configtree_data
                or field_name in self._configtree_data
                or value is not None
            ):
                if key != field_name:
                    result.pop(field_name, None)
                if isinstance(value, (dict, list)) and isinstance(
                    result.get(key), type(value)
                ):
                    result[key] = self._merge_alias_values(result[key], value)
                else:
                    result[key] = value
        return self._clean_alias_values(result)

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        if self._configtree_data is None:
            self._configtree_data = self._load_data()
        alias = field.validation_alias or field.alias
        aliases = alias.choices if isinstance(alias, AliasChoices) else [alias]
        for candidate in [*aliases, field_name]:
            if isinstance(candidate, str) and candidate in self._configtree_data:
                value = self._configtree_data[candidate]
                # A settings model with an alias may not accept field names.
                output_key = candidate
                if candidate == field_name:
                    target = aliases[0] if aliases else None
                    if isinstance(target, str):
                        output_key = target
                    elif isinstance(target, AliasPath):
                        nested = value
                        for component in reversed(target.path[1:]):
                            if isinstance(component, str):
                                nested = {component: nested}
                            else:
                                wrapped = [PydanticUndefined] * max(
                                    component + 1, -component
                                )
                                wrapped[component] = nested
                                nested = wrapped
                        return nested, target.path[0], True
                return value, output_key, isinstance(value, (dict, list))
            if isinstance(candidate, AliasPath):
                value = candidate.search_dict_for_path(self._configtree_data)
                if value is not PydanticUndefined:
                    # Preserve the alias path input shape for model validation.
                    first = candidate.path[0]
                    return self._configtree_data[first], first, True
        return None, field_name, False

    @staticmethod
    def _merge_alias_values(existing: Any, incoming: Any) -> Any:
        if incoming is PydanticUndefined:
            return existing
        if isinstance(existing, dict) and isinstance(incoming, dict):
            result = dict(existing)
            for key, value in incoming.items():
                result[key] = ConfigTreeSource._merge_alias_values(
                    result.get(key, PydanticUndefined), value
                )
            return result
        if isinstance(existing, list) and isinstance(incoming, list):
            return [
                ConfigTreeSource._merge_alias_values(
                    existing[index] if index < len(existing) else PydanticUndefined,
                    incoming[index] if index < len(incoming) else PydanticUndefined,
                )
                for index in range(max(len(existing), len(incoming)))
            ]
        return incoming

    @staticmethod
    def _clean_alias_values(value: Any) -> Any:
        if value is PydanticUndefined:
            return None
        if isinstance(value, list):
            return [ConfigTreeSource._clean_alias_values(item) for item in value]
        if isinstance(value, dict):
            return {
                key: ConfigTreeSource._clean_alias_values(item)
                for key, item in value.items()
            }
        return value
