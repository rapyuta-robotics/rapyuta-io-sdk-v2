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

"""Safe YAML construction with normalized malformed scalar errors."""

import yaml


def load_documents(content: str | bytes) -> list[object]:
    """Read safe documents without extending handling into model validation."""
    try:
        return list(yaml.safe_load_all(content))
    except (AttributeError, IndexError, KeyError, ValueError):
        # Built-in scalar constructors can raise native exceptions for invalid
        # explicitly tagged values. Retain the parser error boundary only here.
        msg = "invalid YAML scalar"
        raise yaml.YAMLError(msg) from None
