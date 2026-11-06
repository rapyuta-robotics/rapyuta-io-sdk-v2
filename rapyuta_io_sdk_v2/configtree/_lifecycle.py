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

"""Commit preparation and original-error recovery details."""

from rapyuta_io_sdk_v2.configtree.exceptions import InputReason, input_error
from rapyuta_io_sdk_v2.models.configtree import ConfigTreeRevision


def prepare_commit(
    client: object, body: ConfigTreeRevision | None, default: str
) -> ConfigTreeRevision:
    """Copy a commit body and fill only absent author/message values."""
    commit = body.model_copy(deep=True) if body is not None else ConfigTreeRevision()
    if commit.author is None:
        commit.author = (
            getattr(client.config, "email", None) or ""
        ).strip() or "rapyuta-io-sdk-v2"
    if commit.message is None:
        commit.message = default
    if not commit.author.strip() or not commit.message.strip():
        raise input_error(InputReason.COMMIT_AUTHOR_AND_MESSAGE_MUST_BE_NONBLANK)
    return commit


def annotate(error: BaseException, stage: str, revision_id: str | None = None) -> None:
    """Attach recovery context to an original exception or cancellation."""
    if (
        getattr(error, "configtree_stage", None) == stage
        and getattr(error, "configtree_revision_id", None) == revision_id
    ):
        return
    error.configtree_stage = stage
    if revision_id:
        error.configtree_revision_id = revision_id
    error.add_note(
        f"Configtree stage: {stage}; revision ID: {revision_id or 'unknown'}"
    )
