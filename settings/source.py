import json
import ast
from typing import Any, Type, Dict
from benedict import benedict
from munch import Munch

import yaml
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from rapyuta_io_sdk_v2 import Client, Configuration
import base64


class ConfigTreeSource(PydanticBaseSettingsSource):
    def __init__(
        self,
        settings_cls: Type["BaseSettings"],
        config: Configuration,
        tree_name: str = "default",
        key_prefix: str = "",
        local_file: str = None,
    ):
        super().__init__(settings_cls)
        self.client = Client(config=config)
        self.tree_name = tree_name
        self.local_file = local_file
        self._top_prefix = key_prefix

        # ? Placeholder for the configuration tree data
        self.config_tree = None

        # * Load the configuration tree
        self.load_config_tree()

        processed_data = self._process_config_tree(raw_data=self.config_tree)

        if processed_data is None:
            raise ValueError("processed_data cannot be None")

        self._configtree_data = benedict(processed_data).unflatten(separator="/")

    # * Methods to fetch Configtree
    def fetch_from_api(self):
        """
        Load the configuration tree from an external API.
        """
        try:
            response = self.client.get_configtree(
                name=self.tree_name,
                include_data=True,
                content_types="kv",
                with_project=False,
            )
            config_tree_response = Munch.toDict(response).get("keys")
            self.config_tree = self._extract_data_api(input_data=config_tree_response)
        except Exception as e:
            raise ValueError(f"Failed to fetch configuration tree from API: {e}")

    def load_from_local_file(self):
        """
        Load the configuration tree from a local JSON or YAML file.
        """
        if not self.local_file:
            raise ValueError("No local file path provided for configuration tree.")

        try:
            with open(self.local_file, "r") as file:
                if self.local_file.endswith(".json"):
                    self.config_tree = self._extract_data_local(json.load(file))
                elif self.local_file.endswith(".yaml") or self.local_file.endswith(
                    ".yml"
                ):
                    self.config_tree = self._extract_data_local(yaml.safe_load(file))
                else:
                    raise ValueError(
                        "Unsupported file format. Use .json or .yaml/.yml."
                    )
        except FileNotFoundError:
            raise ValueError(f"Local file '{self.local_file}' not found.")
        except Exception as e:
            raise ValueError(f"Failed to load configuration tree from file: {e}")

    def load_config_tree(self):
        if self.local_file:
            self.load_from_local_file()

        else:
            self.fetch_from_api()

    # * Methods to process the tree
    def _extract_data_api(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            key: self._decode_and_convert(value.get("data"))
            for key, value in input_data.items()
            if "data" in value
        }

    def _decode_and_convert(self, encoded_data: str) -> Any:
        decoded_data = base64.b64decode(encoded_data).decode("utf-8")

        try:
            # Safely evaluate the decoded string to Python data structures (e.g., lists, dicts)
            return ast.literal_eval(decoded_data)
        except (ValueError, SyntaxError):
            return decoded_data

    def _extract_data_local(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        for key, value in input_data.items():
            if isinstance(value, dict):
                if "value" in value:
                    input_data[key] = value.get("value")
                else:
                    self._extract_data_local(value)
        return input_data

    # * This method is extracting the data from the raw data and removing the top level prefix
    def _process_config_tree(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        prefix_length = len(self._top_prefix)

        if prefix_length == 0:
            return raw_data

        for key in raw_data:
            processed_key = key[prefix_length + 1 :]
            d[processed_key] = raw_data[key]

        return d

    def __call__(self) -> dict[str, Any]:
        if self.config_tree is None:
            raise ValueError("Configuration tree is not loaded.")
        return self._configtree_data

    def get_field_value(self, field_name: str) -> Any:
        if self.config_tree is None:
            raise ValueError("Configuration tree is not loaded.")
        return self.config_tree.get(field_name, None)
