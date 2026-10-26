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

"""Root-confined chart preparation and temporary archive extraction."""

from __future__ import annotations

import bz2
import io
import lzma
import stat
import tarfile
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import yaml
from pydantic import ValidationError

from rapyuta_io_sdk_v2.apply.errors import ApplierValidationError
from rapyuta_io_sdk_v2.apply.source import ManifestSource
from rapyuta_io_sdk_v2.chart._yaml import load_documents
from rapyuta_io_sdk_v2.chart.errors import ChartLoadError
from rapyuta_io_sdk_v2.models.chart import ChartEntry, ChartMetadata, ChartSource

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.apply.applier import Applier, AsyncApplier
    from rapyuta_io_sdk_v2.chart.source import ChartInputs
    from rapyuta_io_sdk_v2.models.applier import ApplierOptions

_STREAM_CHUNK = 64 * 1024
_XZ_HEADER = b"\xfd7zXZ\x00"
_ARCHIVE_ERRORS = (OSError, EOFError, tarfile.TarError, zlib.error, lzma.LZMAError)

try:
    from compression.zstd import ZstdError
except ImportError:
    # Python 3.13 and builds without Zstandard cannot accept this format.
    pass
else:
    _ARCHIVE_ERRORS += (ZstdError,)


@dataclass(frozen=True)
class Preparation:
    """One immutable load request shared across acquisition and preparation."""

    source: ChartSource
    inputs: ChartInputs
    options: ApplierOptions
    facade: type[Applier | AsyncApplier]
    entry: ChartEntry | None = None

    @property
    def origin(self) -> str:
        """Return the original caller-selected source rather than a staging path."""
        return str(self.source.path or self.source.selector)


@dataclass(frozen=True)
class PreparedChart:
    """Complete prepared data with no remaining filesystem or client lifetime."""

    request: Preparation
    metadata: ChartMetadata
    delegate: Applier | AsyncApplier
    template_paths: tuple[str, ...]
    root: Path


def _ordinary_path(path: Path, origin: str) -> None:
    mode = path.lstat().st_mode
    if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
        error = ChartLoadError("source", "unsafe_path", origin)
        raise error


def _validate_tree(root: Path, origin: str) -> None:
    _ordinary_path(root, origin)
    for directory, dirs, files in root.walk(on_error=_raise_os_error):
        for name in (*dirs, *files):
            _ordinary_path(directory / name, origin)


def _validate_source_path(path: Path, origin: str) -> None:
    for parent in reversed(path.absolute().parents):
        _ordinary_path(parent, origin)
    _ordinary_path(path, origin)


def _raise_os_error(error: OSError) -> None:
    raise error


def _metadata(root: Path, request: Preparation) -> ChartMetadata:
    try:
        documents = load_documents((root / "Chart.yaml").read_text(encoding="utf-8"))
        if len(documents) != 1 or not isinstance(documents[0], dict):
            error = ChartLoadError("metadata", "invalid_metadata", request.origin)
            raise error
        result = ChartMetadata.model_validate(documents[0])
    except (OSError, UnicodeError, yaml.YAMLError, ValidationError):
        error = ChartLoadError("metadata", "invalid_metadata", request.origin)
        raise error from None
    if request.entry is not None and (
        result.name != request.entry.name or result.version != request.entry.version
    ):
        error = ChartLoadError("metadata", "identity_mismatch", request.origin)
        raise error
    return result


def _supported_template(path: Path, root: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in {".yaml", ".yml", ".json"}
        and all(not part.startswith(".") for part in path.relative_to(root).parts)
    )


def _templates(root: Path, origin: str) -> tuple[Path, ...]:
    directory = root / "templates"
    if not directory.is_dir():
        error = ChartLoadError("source", "missing_templates", origin)
        raise error
    paths = sorted(
        (p for p in directory.rglob("*") if _supported_template(p, root)),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    if not paths:
        error = ChartLoadError("source", "missing_templates", origin)
        raise error
    return tuple(paths)


def _manifest_source(
    request: Preparation, root: Path, paths: tuple[Path, ...]
) -> ManifestSource:
    inputs = request.inputs
    return ManifestSource(
        files=paths,
        values=inputs.values or (root / "values.yaml",),
        secrets=inputs.secrets,
        rio=inputs.rio,
        interface_resolver=inputs.interface_resolver,
    )


def add_source_note(error: Exception, root: Path, origin: str) -> None:
    """Supplement existing Apply diagnostics without rewriting their attributes."""
    relative = ""
    if isinstance(error, ApplierValidationError) and error.source and error.source.path:
        try:
            relative = str(Path(error.source.path).relative_to(root))
        except ValueError:
            relative = error.source.path
    detail = relative or "prepared collection"
    note = f"Chart source: {origin}; template/value source: {detail}"
    if note not in getattr(error, "__notes__", ()):
        error.add_note(note)


def _prepare_directory(request: Preparation, root: Path) -> PreparedChart:
    _validate_tree(root, request.origin)
    metadata = _metadata(root, request)
    paths = _templates(root, request.origin)
    try:
        delegate = request.facade(
            _manifest_source(request, root, paths), request.options
        )
    except ApplierValidationError as error:
        add_source_note(error, root, request.origin)
        raise
    return PreparedChart(
        request,
        metadata,
        delegate,
        tuple(p.relative_to(root).as_posix() for p in paths),
        root,
    )


def _member_path(member: tarfile.TarInfo, origin: str) -> PurePosixPath:
    path = PurePosixPath(member.name)
    if path.is_absolute() or ".." in path.parts or "\\" in member.name:
        error = ChartLoadError("archive", "unsafe_member", origin)
        raise error
    if not (member.isfile() or member.isdir()):
        error = ChartLoadError("archive", "unsafe_member", origin)
        raise error
    return path


def _inventory(archive: tarfile.TarFile, origin: str) -> None:
    entries: dict[PurePosixPath, bool] = {}
    for member in archive.getmembers():
        path = _member_path(member, origin)
        if path in entries:
            error = ChartLoadError("archive", "duplicate_member", origin)
            raise error
        entries[path] = member.isdir()
    for path in entries:
        if any(parent in entries and not entries[parent] for parent in path.parents):
            error = ChartLoadError("archive", "path_collision", origin)
            raise error


def _archive_root(staging: Path, origin: str) -> Path:
    candidates = [p.parent for p in staging.glob("*/Chart.yaml") if p.is_file()]
    if (staging / "Chart.yaml").is_file():
        candidates.append(staging)
    if len(candidates) != 1:
        error = ChartLoadError("archive", "ambiguous_root", origin)
        raise error
    return candidates[0]


def _next_compressed_stream(source: io.BytesIO, pending: bytes, *, xz: bool) -> bytes:
    if not xz:
        return pending or source.read(_STREAM_CHUNK)
    # XZ permits zero padding in multiples of four between/after streams.
    padding = 0
    while True:
        pending = pending or source.read(_STREAM_CHUNK)
        remaining = pending.lstrip(b"\x00")
        padding += len(pending) - len(remaining)
        if remaining or not pending:
            if padding % 4:
                msg = "invalid XZ stream padding"
                raise lzma.LZMAError(msg)
            return remaining
        pending = b""


def _required_compressed_chunk(source: io.BytesIO) -> bytes:
    pending = source.read(_STREAM_CHUNK)
    if not pending:
        msg = "incomplete compressed chart stream"
        raise EOFError(msg)
    return pending


def _validate_compressed_members(
    data: bytes,
    factory: type[bz2.BZ2Decompressor | lzma.LZMADecompressor],
) -> None:
    # File readers can silently ignore a corrupt trailing stream. Check every
    # member with the public incremental decoder, bounding decompressed output.
    source = io.BytesIO(data)
    decoder = factory()
    pending = source.read(_STREAM_CHUNK)
    while True:
        decoder.decompress(pending, max_length=_STREAM_CHUNK)
        if decoder.eof:
            pending = _next_compressed_stream(
                source, decoder.unused_data, xz=data.startswith(_XZ_HEADER)
            )
            if not pending:
                return
            decoder = factory()
        elif decoder.needs_input:
            pending = _required_compressed_chunk(source)
        else:
            pending = b""


def _validate_archive_stream(archive: tarfile.TarFile, data: bytes) -> None:
    if isinstance(archive.fileobj, bz2.BZ2File):
        _validate_compressed_members(data, bz2.BZ2Decompressor)
    elif isinstance(archive.fileobj, lzma.LZMAFile):
        _validate_compressed_members(data, lzma.LZMADecompressor)
    else:
        # Tar end markers can precede the gzip checksum/trailer. Reading to
        # decompressor EOF also validates concatenated gzip members.
        while archive.fileobj.read(_STREAM_CHUNK):
            pass


def _extract_archive(archive: tarfile.TarFile, root: Path, origin: str) -> None:
    try:
        archive.extractall(root, filter="data")
    except (OverflowError, ValueError):
        # Invalid PAX timestamps can fail numeric conversion inside os.utime.
        error = ChartLoadError("archive", "invalid_archive", origin)
        raise error from None


def prepare_archive(request: Preparation, data: bytes) -> PreparedChart:
    """Extract and eagerly prepare an archive before releasing owned artifacts."""
    try:
        with TemporaryDirectory(prefix="rio-chart-") as temporary:
            root = Path(temporary)
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
                _inventory(archive, request.origin)
                _validate_archive_stream(archive, data)
                _extract_archive(archive, root, request.origin)
            return _prepare_directory(request, _archive_root(root, request.origin))
    except _ARCHIVE_ERRORS:
        error = ChartLoadError("archive", "invalid_archive", request.origin)
        raise error from None


def prepare_local(request: Preparation) -> PreparedChart:
    """Load only explicitly tagged directories/archives; never guess a reference."""
    path = request.source.path
    if path is None:
        error = ChartLoadError("source", "missing_path", request.origin)
        raise error
    try:
        _validate_source_path(path, request.origin)
        if request.source.kind == "directory":
            return _prepare_directory(request, path.resolve())
        return prepare_archive(request, path.read_bytes())
    except OSError:
        error = ChartLoadError("source", "unreadable_source", request.origin)
        raise error from None
