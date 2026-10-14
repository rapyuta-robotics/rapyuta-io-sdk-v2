# Copyright 2026 Rapyuta Robotics

"""Metadata preflight, source identity checks and bounded file classification."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from rapyuta_io_sdk_v2._parameter_api import (
    CHILD_PATH,
    child_path,
    parameter_base,
    tree_name,
)
from rapyuta_io_sdk_v2.exceptions import ValidationError
from rapyuta_io_sdk_v2.helpers._parameter_upload import disk_work
from rapyuta_io_sdk_v2.models.parameter import (
    ParameterNodeType,
    ParameterSkippedEntry,
    ParameterSkipReason,
    ParameterUploadMetadata,
    ParameterUploadOptions,
)

if TYPE_CHECKING:
    import httpx

    from rapyuta_io_sdk_v2.config import Configuration

INLINE_LIMIT = 131072
BLOCK_SIZE = 4194304
MAX_BLOB_SIZE = 209715200000


class SourceError(ValueError):
    """A local error retaining its source-relative path."""

    def __init__(self, path: str, message: str) -> None:
        """Retain a path alongside the validation message."""
        self.path = path
        super().__init__(message)


@dataclass(frozen=True)
class SourceEntry:
    """One metadata-only entry and the directory identities leading to it."""

    path: Path
    tree_path: str
    node_type: ParameterNodeType
    identity: os.stat_result
    ancestors: tuple[tuple[Path, os.stat_result], ...]


@dataclass(frozen=True)
class SourceManifest:
    """Selected trees, sorted entries and skips; no file bytes retained."""

    selected_trees: tuple[str, ...]
    entries: tuple[SourceEntry, ...]
    skipped_entries: tuple[ParameterSkippedEntry, ...]
    roots: tuple[SourceEntry, ...] = ()


@dataclass(frozen=True)
class ClassifiedFile:
    """One classified file with original inline text or prehashed blob metadata."""

    entry: SourceEntry
    text: str | None
    checksum: str
    content_type: str
    content_encoding: str | None

    @property
    def metadata(self) -> ParameterUploadMetadata:
        """Return typed binary preparation headers."""
        return ParameterUploadMetadata(
            checksum=self.checksum,
            content_type=self.content_type,
            content_encoding=self.content_encoding,
        )


def validate_storage_client(client: httpx.Client | httpx.AsyncClient | None) -> None:
    """Reject unsafe injected transports before remote mutations."""
    if client is None:
        return
    allowed = {"accept", "accept-encoding", "connection", "user-agent"}
    if client.auth or client.cookies or client.follow_redirects:
        message = "Storage client must have no auth/cookies and disable redirects"
        raise ValueError(message)
    if set(client.headers) - allowed or client.is_closed:
        message = "Storage client must be open and have only default public headers"
        raise ValueError(message)


def preflight(
    config: Configuration, rootdir: str | Path, options: ParameterUploadOptions
) -> SourceManifest:
    """Validate source metadata, selection and platform setup before mutations."""
    parameter_base(config)
    if not config.project_guid or not config.project_guid.strip():
        message = "Parameter uploads require project_guid"
        raise ValueError(message)
    headers = config.get_headers()
    if not headers.get("Authorization", "").removeprefix("Bearer ").strip():
        message = "Parameter uploads require auth_token"
        raise ValueError(message)
    options = ParameterUploadOptions.model_validate(options.model_dump())
    return _Scan(Path(rootdir).expanduser().absolute(), options).run()


def _readable(path: Path, identity: os.stat_result) -> None:
    if not identity.st_mode & 0o444:
        raise SourceError(str(path), "Source is not readable")
    if stat.S_ISDIR(identity.st_mode) and not identity.st_mode & 0o111:
        raise SourceError(str(path), "Source directory is not searchable")


@dataclass
class _Scan:
    root: Path
    options: ParameterUploadOptions
    entries: list[SourceEntry] = field(default_factory=list)
    skipped: list[ParameterSkippedEntry] = field(default_factory=list)
    roots: list[SourceEntry] = field(default_factory=list)

    def skip(self, path: Path, reason: ParameterSkipReason) -> None:
        self.skipped.append(
            ParameterSkippedEntry(
                path=path.relative_to(self.root).as_posix(), reason=reason
            )
        )

    def run(self) -> SourceManifest:
        identity = self.root.lstat()
        if not stat.S_ISDIR(identity.st_mode):
            raise SourceError(str(self.root), "Source must be a directory, not a link")
        _readable(self.root, identity)
        names = self._select()
        ancestors = ((self.root, identity),)
        for name in names:
            tree = self.root / name
            self.walk(tree, ancestors)
        return SourceManifest(
            tuple(names), tuple(self.entries), tuple(self.skipped), tuple(self.roots)
        )

    def _select(self) -> list[str]:
        names = []
        for path in sorted(self.root.iterdir()):
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                names.append(path.name)
            else:
                self.skip(path, _skip_reason(mode, root_file=True))
        self._unmatched(names)
        selected = [
            name
            for name in names
            if not self.options.tree_names or name in self.options.tree_names
        ]
        if self.options.tree_names and not selected:
            raise SourceError(str(self.root), "No requested Parameter trees match")
        return selected

    def _unmatched(self, names: list[str]) -> None:
        for name in self.options.tree_names:
            _validate_path(name)
            if name not in names:
                self.skipped.append(
                    ParameterSkippedEntry(
                        path=name, reason=ParameterSkipReason.UNMATCHED_TREE
                    )
                )

    def walk(
        self, directory: Path, ancestors: tuple[tuple[Path, os.stat_result], ...]
    ) -> None:
        identity = directory.lstat()
        if not stat.S_ISDIR(identity.st_mode):
            raise SourceError(str(directory), "Source directory changed")
        _readable(directory, identity)
        relative = directory.relative_to(self.root).as_posix()
        _validate_path(relative, folder=self.options.as_folder)
        self.validate_legacy_path(relative)
        parents = (*ancestors, (directory, identity))
        entry = SourceEntry(
            directory, relative, self.directory_type(relative), identity, ancestors
        )
        if "/" in relative:
            self.entries.append(entry)
        else:
            self.roots.append(entry)
        for path in self.children(directory, relative):
            self._entry(path, parents)

    def validate_legacy_path(self, relative: str) -> None:
        if self.options.as_folder or "/" not in relative:
            return
        child = relative.partition("/")[2]
        if "." in child.rsplit("/", 1)[-1]:
            raise SourceError(relative, "Legacy directory nodes cannot have extensions")
        attributes = child.split("/")[::2]
        if len(set(attributes)) != len(attributes):
            raise SourceError(
                relative, "Legacy attribute names cannot repeat in a branch"
            )

    def directory_type(self, relative: str) -> ParameterNodeType:
        if "/" not in relative:
            return ParameterNodeType.VALUE
        if self.options.as_folder:
            return ParameterNodeType.FOLDER
        return (
            ParameterNodeType.ATTRIBUTE
            if relative.count("/") % 2
            else ParameterNodeType.VALUE
        )

    def children(self, directory: Path, relative: str) -> list[Path]:
        paths = sorted(directory.iterdir())
        if (
            self.options.as_folder
            or self.directory_type(relative) != ParameterNodeType.VALUE
        ):
            return paths
        directories = sum(stat.S_ISDIR(path.lstat().st_mode) for path in paths)
        if directories > 1:
            raise SourceError(
                relative, "Legacy ValueNode allows at most one AttributeNode child"
            )
        return paths

    def _entry(
        self, path: Path, ancestors: tuple[tuple[Path, os.stat_result], ...]
    ) -> None:
        identity = path.lstat()
        if stat.S_ISDIR(identity.st_mode):
            self.walk(path, ancestors)
        elif stat.S_ISREG(identity.st_mode):
            self._file(path, identity, ancestors)
        else:
            self.skip(path, _skip_reason(identity.st_mode))

    def _file(
        self,
        path: Path,
        identity: os.stat_result,
        ancestors: tuple[tuple[Path, os.stat_result], ...],
    ) -> None:
        relative = path.relative_to(self.root).as_posix()
        parent = relative.rpartition("/")[0]
        if (
            not self.options.as_folder
            and self.directory_type(parent) == ParameterNodeType.ATTRIBUTE
        ):
            self.skip(path, ParameterSkipReason.LEGACY_ATTRIBUTE_FILE)
            return
        _validate_path(relative)
        _readable(path, identity)
        if identity.st_size > MAX_BLOB_SIZE:
            raise SourceError(
                relative, f"File exceeds maximum supported size {MAX_BLOB_SIZE} bytes"
            )
        entry = SourceEntry(path, relative, ParameterNodeType.FILE, identity, ancestors)
        read_chunk(entry, 0, 0)
        self.entries.append(entry)


def _skip_reason(mode: int, *, root_file: bool = False) -> ParameterSkipReason:
    if stat.S_ISLNK(mode):
        return ParameterSkipReason.SYMBOLIC_LINK
    if stat.S_ISREG(mode) and root_file:
        return ParameterSkipReason.ROOT_FILE
    return ParameterSkipReason.SPECIAL_ENTRY


def _validate_path(relative: str, *, folder: bool = False) -> None:
    name, _, child = relative.partition("/")
    try:
        tree_name(name)
        if child:
            child_path(relative)
    except ValidationError as error:
        raise SourceError(relative, str(error)) from error
    normalized = "/" + child + ("/" if folder else "")
    if child and not CHILD_PATH.fullmatch(normalized):
        raise SourceError(relative, "Unsupported Parameter child path")


def _same_identity(
    current: os.stat_result, original: os.stat_result, *, directory: bool = False
) -> bool:
    if directory:
        return (current.st_dev, current.st_ino, current.st_mode) == (
            original.st_dev,
            original.st_ino,
            original.st_mode,
        )
    return (
        current.st_dev,
        current.st_ino,
        current.st_mode,
        current.st_size,
        current.st_mtime_ns,
        current.st_ctime_ns,
    ) == (
        original.st_dev,
        original.st_ino,
        original.st_mode,
        original.st_size,
        original.st_mtime_ns,
        original.st_ctime_ns,
    )


def check_source(entry: SourceEntry) -> None:
    """Recheck the entry and all inspected ancestors without following links."""
    for path, identity in entry.ancestors:
        if not _same_identity(path.lstat(), identity, directory=True):
            raise SourceError(entry.tree_path, "Source ancestor changed")
    if not _same_identity(
        entry.path.lstat(),
        entry.identity,
        directory=entry.node_type != ParameterNodeType.FILE,
    ):
        raise SourceError(entry.tree_path, "Source changed after preflight")


def read_chunk(entry: SourceEntry, offset: int, length: int = BLOCK_SIZE) -> bytes:
    """Read a bounded chunk with a worker-owned handle and identity checks."""
    check_source(entry)
    with entry.path.open("rb") as stream:
        if not _same_identity(os.fstat(stream.fileno()), entry.identity):
            raise SourceError(entry.tree_path, "Opened source changed")
        stream.seek(offset)
        content = stream.read(length)
    check_source(entry)
    return content


def file_checksum(entry: SourceEntry) -> str:
    """Hash original bytes incrementally; MD5 is a protocol checksum."""
    digest = hashlib.md5(usedforsecurity=False)
    for offset in range(0, entry.identity.st_size, BLOCK_SIZE):
        digest.update(read_chunk(entry, offset))
    check_source(entry)
    return digest.hexdigest()


def _structured(entry: SourceEntry) -> tuple[str, str] | None:
    if entry.identity.st_size > INLINE_LIMIT or entry.path.suffix not in {
        ".yaml",
        ".json",
    }:
        return None
    text = read_chunk(entry, 0, INLINE_LIMIT).decode("utf-8")
    mime = "application/json" if entry.path.suffix == ".json" else "text/yaml"
    parsed = json.loads(text) if mime == "application/json" else yaml.safe_load(text)
    if mime == "text/yaml" and not isinstance(parsed, dict):
        raise SourceError(entry.tree_path, "Inline YAML must contain a mapping")
    payload = {"type": "FileNode", "data": text, "contentType": mime}
    if len(json.dumps(payload)) + 200 > INLINE_LIMIT:
        return None
    return text, mime


def classify_file(entry: SourceEntry) -> ClassifiedFile:
    """Validate small structured candidates before estimating stored size."""
    structured = _structured(entry)
    checksum = file_checksum(entry)
    return _classified(entry, structured, checksum)


def _classified(
    entry: SourceEntry, structured: tuple[str, str] | None, checksum: str
) -> ClassifiedFile:
    if structured is not None:
        return ClassifiedFile(entry, structured[0], checksum, structured[1], None)
    mime, encoding = mimetypes.MimeTypes().guess_type(str(entry.path))
    if not mime or mime in {"application/json", "text/yaml"}:
        mime = "application/octet-stream"
    return ClassifiedFile(entry, None, checksum, mime, encoding)


async def classify_file_async(entry: SourceEntry) -> ClassifiedFile:
    """Classify with cancellation checkpoints between bounded prehash reads."""
    structured = await disk_work(_structured, entry)
    digest = hashlib.md5(usedforsecurity=False)
    for offset in range(0, entry.identity.st_size, BLOCK_SIZE):
        content = await disk_work(read_chunk, entry, offset)
        await disk_work(digest.update, content)
        del content
    await disk_work(check_source, entry)
    return _classified(entry, structured, digest.hexdigest())
