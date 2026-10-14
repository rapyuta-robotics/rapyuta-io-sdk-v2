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

"""Reusable resource application helpers."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.apply.applier import Applier, AsyncApplier
    from rapyuta_io_sdk_v2.apply.secrets import (
        async_decrypt_secret_file,
        decrypt_secret_file,
    )
    from rapyuta_io_sdk_v2.apply.source import ManifestSource


def __getattr__(name: str) -> object:
    """Load the public facades lazily to keep resource imports acyclic."""
    if name in {"Applier", "AsyncApplier"}:
        from rapyuta_io_sdk_v2.apply.applier import Applier, AsyncApplier  # noqa: PLC0415

        return Applier if name == "Applier" else AsyncApplier
    if name == "ManifestSource":
        from rapyuta_io_sdk_v2.apply.source import ManifestSource  # noqa: PLC0415

        return ManifestSource
    if name in {"decrypt_secret_file", "async_decrypt_secret_file"}:
        from rapyuta_io_sdk_v2.apply.secrets import (  # noqa: PLC0415
            async_decrypt_secret_file,
            decrypt_secret_file,
        )

        return (
            decrypt_secret_file
            if name == "decrypt_secret_file"
            else async_decrypt_secret_file
        )
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


__all__ = [
    "Applier",
    "AsyncApplier",
    "ManifestSource",
    "async_decrypt_secret_file",
    "decrypt_secret_file",
]
