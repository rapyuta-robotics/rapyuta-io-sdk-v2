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

"""Domain errors for configuration tree workflows."""

from enum import StrEnum


class ConfigTreeInputError(ValueError):
    """Invalid named file, content path, or key payload."""

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        key: str | None = None,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        """Keep sanitized file, key, and parser location available to callers."""
        location = f" (line {line}, column {column})" if line is not None else ""
        super().__init__(f"{message}{location}")
        self.file_path = file_path
        self.key = key
        self.line = line
        self.column = column


class ConfigTreeReferenceError(ValueError):
    """Invalid or unresolved tree, revision, or milestone reference."""

    def __init__(self, message: str, *, refspec: str | None = None) -> None:
        """Keep the original reference available for callers."""
        super().__init__(message)
        self.refspec = refspec


class ConfigTreeMergeConflictError(ValueError):
    """Shared keys with incompatible stored data or metadata."""

    def __init__(self, conflicting_keys: list[str]) -> None:
        """Record all conflicting names in sorted order."""
        self.conflicting_keys = sorted(conflicting_keys)
        super().__init__(
            f"Conflicting configuration keys: {', '.join(self.conflicting_keys)}"
        )


class ConfigTreeMutationError(RuntimeError):
    """A platform mutation did not return an affirmative acknowledgement."""


def input_error(
    message: str,
    *,
    file_path: str | None = None,
    key: str | None = None,
    line: int | None = None,
    column: int | None = None,
) -> ConfigTreeInputError:
    """Build a sanitized input error with optional path context."""
    return ConfigTreeInputError(
        message, file_path=file_path, key=key, line=line, column=column
    )


def reference_error(
    message: str, *, refspec: str | None = None
) -> ConfigTreeReferenceError:
    """Build a reference error without exposing configuration values."""
    return ConfigTreeReferenceError(message, refspec=refspec)


def mutation_error(message: str) -> ConfigTreeMutationError:
    """Build an unsuccessful mutation error."""
    return ConfigTreeMutationError(message)


class InputReason(StrEnum):
    """Sanitized reasons for input error."""

    AMBIGUOUS_CONFIGURATION_PATH = "Ambiguous configuration path"
    AT_LEAST_ONE_CONFIGURATION_FILE_IS_REQUIRED = (
        "At least one configuration file is required"
    )
    COMMIT_AUTHOR_AND_MESSAGE_MUST_BE_NONBLANK = (
        "Commit author and message must be nonblank"
    )
    CONFIGURATION_FILE_HAS_NO_KEYS = "Configuration file has no keys"
    CONFIGURATION_FILE_MUST_CONTAIN_A_NONEMPTY_MAPPING = (
        "Configuration file must contain a nonempty mapping"
    )
    CONFIGURATION_MAPPING_KEYS_MUST_BE_STRINGS = (
        "Configuration mapping keys must be strings"
    )
    CYCLIC_CONFIGURATION_VALUE = "Cyclic configuration value"
    DUPLICATE_CONFIGURATION_KEY = "Duplicate configuration key"
    DUPLICATE_CONFIGURATION_MAPPING_KEY = "Duplicate configuration mapping key"
    DUPLICATE_OR_INVALID_CONFIGURATION_FILE_STEM = (
        "Duplicate or invalid configuration file stem"
    )
    FILES_MUST_BE_AN_ITERABLE_OF_NAMED_PATHS = (
        "Files must be an iterable of named paths"
    )
    INVALID_CONFIGURATION_DOCUMENT = "Invalid configuration document"
    INVALID_CONFIGURATION_KEY_METADATA = "Invalid configuration key metadata"
    INVALID_CONFIGURATION_KEY_PATH = "Invalid configuration key path"
    INVALID_CONFIGURATION_KEY_PAYLOAD = "Invalid configuration key payload"
    INVALID_CONFIGURATION_METADATA = "Invalid configuration metadata"
    INVALID_CONFIGURATION_PATH_COMPONENT = "Invalid configuration path component"
    INVALID_STORED_CONFIGURATION_KEY = "Invalid stored configuration key"
    NON_FINITE_CONFIGURATION_VALUE = "Non-finite configuration value"
    SOURCE_KEY_HAS_INVALID_CONTENT_LENGTH = "Source key has invalid content length"
    UNSUPPORTED_CONFIGURATION_FILE_SUFFIX = "Unsupported configuration file suffix"
    UNSUPPORTED_CONFIGURATION_VALUE_TYPE = "Unsupported configuration value type"


class ReferenceReason(StrEnum):
    """Sanitized reasons for reference error."""

    CREATED_REVISION_HAS_NO_GUID = "Created revision has no GUID"
    INVALID_CONFIGURATION_REFERENCE = "Invalid configuration reference"
    INVALID_MILESTONE_CONTINUATION = "Invalid milestone continuation"
    MILESTONE_MATCHES_MULTIPLE_REVISIONS = "Milestone matches multiple revisions"
    MILESTONE_MATCHES_NO_REVISIONS = "Milestone matches no revisions"
    MILESTONE_REVISION_HAS_NO_GUID = "Milestone revision has no GUID"
    REQUIRED_CONFIGURATION_TREE_SCOPE_IS_MISSING = (
        "Required configuration tree scope is missing"
    )
    SELECTED_CONFIGURATION_KEY_MAP_IS_MISSING = (
        "Selected configuration key map is missing"
    )
    SELECTED_CONFIGURATION_REVISION_IS_MISSING = (
        "Selected configuration revision is missing"
    )
    SELECTED_PARENT_REVISION_IS_UNCOMMITTED = "Selected parent revision is uncommitted"
    SELECTED_REVISION_IDENTITY_DOES_NOT_MATCH = (
        "Selected revision identity does not match"
    )


class MutationReason(StrEnum):
    """Sanitized reasons for mutation error."""

    CONFIGURATION_BATCH_WAS_NOT_ACKNOWLEDGED = (
        "Configuration batch was not acknowledged"
    )
