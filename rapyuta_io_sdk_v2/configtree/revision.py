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

"""Single-use synchronous and asynchronous revision contexts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from rapyuta_io_sdk_v2.configtree._lifecycle import annotate, prepare_commit
from rapyuta_io_sdk_v2.configtree._scope import Scope
from rapyuta_io_sdk_v2.configtree._values import (
    encode_secret_ref,
    encode_value,
    snapshot_values,
    validate_key,
)
from rapyuta_io_sdk_v2.configtree.exceptions import (
    ConfigTreeInputError,
    MutationReason,
    ReferenceReason,
    mutation_error,
    reference_error,
)
from rapyuta_io_sdk_v2.models.configtree import (
    ConfigTreeRevision,
    ConfigValue,
    ConfigValues,
)
from rapyuta_io_sdk_v2.models.configtree_operations import RevisionOptions

if TYPE_CHECKING:
    from types import TracebackType

    from rapyuta_io_sdk_v2 import AsyncClient, Client
    from rapyuta_io_sdk_v2.models.configtree_operations import ConfigContent
    from rapyuta_io_sdk_v2.models.responses import APIResponse


class _BaseRevision:
    """Own local staging, scope, and one revision identity."""

    def __init__(
        self,
        client: Client | AsyncClient,
        tree_name: str,
        *,
        options: RevisionOptions | None = None,
        parent: str | None = None,
        commit_message: str = "Created revision through rapyuta-io-sdk-v2",
        _scope: Scope | None = None,
    ) -> None:
        """Prepare local state without making a platform request.

        Args:
            client: Synchronous or asynchronous SDK client.
            tree_name: Existing destination tree name.
            options: Scope and optional commit settings.
            parent: Optional pinned parent revision GUID.
            commit_message: Default message when committing without one.
            _scope: Workflow-owned immutable scope snapshot.

        Raises:
            ConfigTreeInputError: If the name or commit body is invalid.
            ConfigTreeReferenceError: If the configured scope is missing.
        """
        try:
            validate_key(tree_name)
            self.client = client
            self.tree_name = tree_name
            self.options = options or RevisionOptions()
            self.scope = _scope or Scope.capture(
                client, with_project=self.options.with_project
            )
            self.parent = parent
            self._keys: dict[str, ConfigValue] = {}
            self._revision_id: str | None = None
            self._used = False
            self._commit_body = (
                prepare_commit(client, self.options.commit_body, commit_message)
                if self.options.commit
                else None
            )
        except BaseException as error:
            annotate(error, "prepare")
            raise

    @property
    def keys(self) -> dict[str, ConfigValue]:
        """Return the same editable pending dictionary for this context."""
        return self._keys

    @property
    def revision_id(self) -> str | None:
        """Return the created revision GUID when known."""
        return self._revision_id

    def store(
        self, key: str, value: ConfigContent, *, metadata: dict[str, str] | None = None
    ) -> None:
        """Stage one logical leaf locally, replacing any pending entry.

        Args:
            key: Nonempty slash-separated key path.
            value: Supported JSON-like content or date/datetime value.
            metadata: Optional string-to-string metadata, including empty.

        Raises:
            ConfigTreeInputError: If the path, value, or metadata is invalid.
        """
        validate_key(key)
        try:
            self._keys[key] = encode_value(value, metadata=metadata)
        except ConfigTreeInputError as error:
            if error.key is None:
                error.key = key
            raise

    def store_secret_ref(
        self,
        key: str,
        secret_name: str,
        secret_key: str,
        *,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Stage one leaf that resolves from a Secret, replacing any pending entry.

        The platform (and, for a device deployment, the owning device) resolves
        secret_name/secret_key into the real value on read; this key never
        carries literal data.

        Args:
            key: Nonempty slash-separated key path.
            secret_name: Name of the Secret resource holding the value.
            secret_key: Key within that Secret.
            metadata: Optional string-to-string metadata, including empty.

        Raises:
            ConfigTreeInputError: If the path, secret ref, or metadata is invalid.
        """
        validate_key(key)
        try:
            self._keys[key] = encode_secret_ref(
                secret_name, secret_key, metadata=metadata
            )
        except ConfigTreeInputError as error:
            if error.key is None:
                error.key = key
            raise

    def _start(self) -> ConfigTreeRevision | None:
        if self._used:
            message = "Revision context is single-use"
            raise RuntimeError(message)
        self._used = True
        return ConfigTreeRevision(parent=self.parent) if self.parent else None

    def _created(self, revision: ConfigTreeRevision) -> None:
        guid = revision.metadata.guid if revision.metadata else None
        if not guid:
            raise reference_error(ReferenceReason.CREATED_REVISION_HAS_NO_GUID)
        self._revision_id = guid

    @staticmethod
    def _check_response(response: APIResponse) -> None:
        if response.success is not True or response.error:
            raise mutation_error(
                MutationReason.CONFIGURATION_BATCH_WAS_NOT_ACKNOWLEDGED
            )

    def _snapshot(self) -> ConfigValues:
        try:
            return snapshot_values(self._keys)
        except BaseException as error:
            annotate(error, "validate", self.revision_id)
            raise


class Revision(_BaseRevision):
    """Create, batch-store, and optionally commit one synchronous revision.

    Construct with a ``Client``, tree name, optional ``RevisionOptions``, and
    optional pinned parent GUID. Inside ``with``, ``keys`` is a stable editable
    dictionary; ``store`` encodes logical leaves without I/O. Normal exit sends
    one batch if nonempty and optionally commits. Entry, validation, transport,
    and commit failures retain their original type and carry recovery context.
    """

    def __enter__(self) -> Self:
        """Create the revision and retain its returned GUID."""
        body = self._start()
        try:
            self._created(
                self.client.create_revision(
                    self.tree_name, body=body, **self.scope.headers()
                )
            )
        except BaseException as error:
            annotate(error, "create", self.revision_id)
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Finalize only a successful body; retain original errors with stage."""
        if exc_value is not None:
            annotate(exc_value, "body", self.revision_id)
            return False
        self._finish(self._snapshot())
        return False

    def _finish(self, values: ConfigValues) -> None:
        try:
            if values.root:
                self._check_response(
                    self.client.put_keys_in_revision(
                        self.tree_name, self.revision_id, values, **self.scope.headers()
                    )
                )
        except BaseException as error:
            annotate(error, "store", self.revision_id)
            raise
        try:
            if self._commit_body is not None:
                self.client.commit_revision(
                    self.tree_name,
                    self.revision_id,
                    self._commit_body,
                    **self.scope.headers(),
                )
        except BaseException as error:
            annotate(error, "commit", self.revision_id)
            raise


class AsyncRevision(_BaseRevision):
    """Await creation, one batch, and optional commit with ``AsyncClient``.

    Use ``async with`` and edit the same local ``keys`` dictionary or call the
    synchronous ``store`` method. Failures and cancellation propagate with the
    known revision GUID and stage attached for recovery.
    """

    async def __aenter__(self) -> Self:
        """Create the revision through the asynchronous client."""
        body = self._start()
        try:
            self._created(
                await self.client.create_revision(
                    self.tree_name, body=body, **self.scope.headers()
                )
            )
        except BaseException as error:
            annotate(error, "create", self.revision_id)
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Snapshot before awaited storage and propagate cancellation."""
        if exc_value is not None:
            annotate(exc_value, "body", self.revision_id)
            return False
        await self._finish(self._snapshot())
        return False

    async def _finish(self, values: ConfigValues) -> None:
        try:
            if values.root:
                self._check_response(
                    await self.client.put_keys_in_revision(
                        self.tree_name, self.revision_id, values, **self.scope.headers()
                    )
                )
        except BaseException as error:
            annotate(error, "store", self.revision_id)
            raise
        try:
            if self._commit_body is not None:
                await self.client.commit_revision(
                    self.tree_name,
                    self.revision_id,
                    self._commit_body,
                    **self.scope.headers(),
                )
        except BaseException as error:
            annotate(error, "commit", self.revision_id)
            raise
