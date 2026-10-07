"""Optional chart repositories and reusable declarative chart workflows."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import quote, urljoin

import httpx
from pydantic import BaseModel, ConfigDict, Field

from rapyuta_io_sdk_v2.apply import Applier, AsyncApplier
from rapyuta_io_sdk_v2.features import require_dependency

DEFAULT_REPOSITORY = (
    "https://rapyuta-robotics.github.io/rapyuta-charts/incubator/index.yaml"
)
BRANCH_REPO_BASE = "https://chartsbranch.blob.core.windows.net/charts-per-branch"
MAX_INDEX_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_EXTRACTED_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10_000


class ChartError(Exception):
    """A repository, metadata, download, or archive cannot be used."""


def branch_repository_url(branch: str) -> str:
    if not branch or any(part in (".", "..") for part in branch.split("/")):
        raise ChartError("A nonempty branch without dot path components is required")
    return f"{BRANCH_REPO_BASE}/{quote(branch, safe='/')}/incubator/index.yaml"


class ChartMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    urls: list[str] = Field(min_length=1)
    description: str | None = None
    created: str | None = None
    api_version: str | None = Field(default=None, alias="apiVersion")
    app_version: str | None = Field(default=None, alias="appVersion")
    digest: str | None = None


class ChartIndex(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    api_version: str | None = Field(default=None, alias="apiVersion")
    entries: dict[str, list[ChartMetadata]]
    generated: str | None = None


def _choose(index: ChartIndex, name: str, version: str | None) -> ChartMetadata:
    if ":" in name:
        if version is not None or name.count(":") != 1:
            raise ChartError("Use name:version or the version argument, not both")
        name, version = name.split(":")
    if not name or version == "":
        raise ChartError("A chart name and nonempty version are required")
    entries = index.entries.get(name, [])
    if version is None and entries:
        return entries[0]
    for entry in entries:
        if entry.version == version:
            return entry
    raise ChartError(f"Chart {name}{':' + version if version else ''} not found")


def _extract(content: bytes, destination: Path, name: str) -> Path:
    if len(content) > MAX_ARCHIVE_BYTES:
        raise ChartError("Chart archive exceeds the download limit")
    try:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
            members = []
            total = 0
            seen = set()
            for member in archive:
                members.append(member)
                if len(members) > MAX_ARCHIVE_MEMBERS:
                    raise ChartError("Chart archive has too many entries")
                path = PurePosixPath(member.name)
                if (
                    path.is_absolute()
                    or PureWindowsPath(member.name).drive
                    or ".." in path.parts
                    or "\\" in member.name
                ):
                    raise ChartError(f"Unsafe chart archive path: {member.name}")
                if not member.isdir() and not member.isfile():
                    raise ChartError(f"Unsupported chart archive entry: {member.name}")
                if member.name in seen:
                    raise ChartError(f"Duplicate chart archive entry: {member.name}")
                seen.add(member.name)
                total += member.size
                if total > MAX_EXTRACTED_BYTES:
                    raise ChartError("Chart archive exceeds the extraction limit")
            # Extract manually after checking every entry. Never follow archive links.
            for member in members:
                target = destination.joinpath(*PurePosixPath(member.name).parts)
                if not target.resolve().is_relative_to(destination.resolve()):
                    raise ChartError(f"Unsafe chart archive path: {member.name}")
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = archive.extractfile(member)
                    if source is None:
                        raise ChartError(f"Cannot read chart entry {member.name}")
                    with source, target.open("wb") as output:
                        while block := source.read(64 * 1024):
                            output.write(block)
    except (tarfile.TarError, OSError) as error:
        raise ChartError(f"Invalid chart archive: {error}") from error
    # A metadata name must not let the caller escape the extraction directory.
    if (
        not name
        or PurePosixPath(name).name != name
        or name in (".", "..")
        or "\\" in name
    ):
        raise ChartError("Invalid chart name")
    root = destination / name
    if not (root / "templates").is_dir():
        raise ChartError(f"Chart archive is missing {name}/templates")
    return root


class _Repository:
    def __init__(
        self,
        configuration: Any,
        url: str | None = None,
        *,
        branch: str | None = None,
        transport: Any = None,
        timeout: float = 30,
    ):
        configuration.features.require("charts")
        configuration.features.require("apply")
        self.yaml = require_dependency("yaml", "charts")
        require_dependency("jinja2", "charts")
        if url and branch:
            raise ValueError("Choose either a repository URL or a branch")
        self.configuration = configuration
        self.url = url or (
            branch_repository_url(branch) if branch is not None else DEFAULT_REPOSITORY
        )
        self.transport = transport
        self.timeout = timeout
        self._owned = transport is None

    def _check(self):
        self.configuration.features.require("charts")
        self.configuration.features.require("apply")


class ChartRepository(_Repository):
    """Repository with bounded downloads; caller-owned HTTP clients stay open."""

    def __init__(self, configuration: Any, url: str | None = None, **kwargs):
        super().__init__(configuration, url, **kwargs)
        if self.transport is None:
            self.transport = httpx.Client(timeout=self.timeout, follow_redirects=True)

    def _fetch(self, url: str, limit: int) -> bytes:
        self._check()
        chunks = []
        size = 0
        with self.transport.stream("GET", url, timeout=self.timeout) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > limit:
                    raise ChartError(f"Download exceeds {limit} bytes")
                chunks.append(chunk)
        return b"".join(chunks)

    def index(self) -> ChartIndex:
        return ChartIndex.model_validate(
            self.yaml.safe_load(self._fetch(self.url, MAX_INDEX_BYTES))
        )

    def find(self, name: str, version: str | None = None) -> Chart:
        return Chart(_choose(self.index(), name, version), self)

    def close(self):
        if self._owned:
            self.transport.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AsyncChartRepository(_Repository):
    def __init__(self, configuration: Any, url: str | None = None, **kwargs):
        super().__init__(configuration, url, **kwargs)
        if self.transport is None:
            self.transport = httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True
            )

    async def _fetch(self, url: str, limit: int) -> bytes:
        self._check()
        chunks = []
        size = 0
        async with self.transport.stream("GET", url, timeout=self.timeout) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > limit:
                    raise ChartError(f"Download exceeds {limit} bytes")
                chunks.append(chunk)
        return b"".join(chunks)

    async def index(self) -> ChartIndex:
        return ChartIndex.model_validate(
            self.yaml.safe_load(await self._fetch(self.url, MAX_INDEX_BYTES))
        )

    async def find(self, name: str, version: str | None = None) -> AsyncChart:
        return AsyncChart(_choose(await self.index(), name, version), self)

    async def aclose(self):
        if self._owned:
            await self.transport.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.aclose()


class _Chart:
    def __init__(self, metadata: ChartMetadata, repository: _Repository):
        self.metadata = metadata
        self.repository = repository
        self._temporary: TemporaryDirectory | None = None
        self.path: Path | None = None

    def _unpack(self, content: bytes) -> Path:
        self._temporary = TemporaryDirectory(prefix="rio-chart-")
        try:
            if self.metadata.digest:
                import hashlib

                actual = hashlib.sha256(content).hexdigest()
                if actual != self.metadata.digest.removeprefix("sha256:"):
                    raise ChartError("Chart archive checksum does not match metadata")
            self.path = _extract(content, Path(self._temporary.name), self.metadata.name)
            return self.path
        except BaseException:
            self.close()
            raise

    def _options(self, options: dict) -> dict:
        if self.path is None:
            raise ChartError("Chart has not been downloaded")
        overrides = options.get("values", ())
        if isinstance(overrides, (dict, str, Path)):
            overrides = [overrides]
        defaults = self.path / "values.yaml"
        options["values"] = ([defaults] if defaults.exists() else []) + list(overrides)
        return options

    def close(self):
        if self._temporary is not None:
            self._temporary.cleanup()
        self._temporary = None
        self.path = None


class Chart(_Chart):
    def download(self) -> Path:
        self.repository._check()
        if self.path is None:
            url = urljoin(self.repository.url, self.metadata.urls[0])
            return self._unpack(self.repository._fetch(url, MAX_ARCHIVE_BYTES))
        return self.path

    def _applier(self, client: Any, options: dict) -> Applier:
        path = self.download()
        return Applier(client, path / "templates", **self._options(options))

    def render(self, client: Any, **options):
        return self._applier(client, options).render()

    def plan(self, client: Any, *, operation: str = "apply", **options):
        return self._applier(client, options).plan(operation=operation)

    def apply(self, client: Any, *, dry_run: bool = False, **options):
        return self._applier(client, options).apply(dry_run=dry_run)

    def delete(self, client: Any, *, dry_run: bool = False, **options):
        return self._applier(client, options).delete(dry_run=dry_run)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AsyncChart(_Chart):
    async def download(self) -> Path:
        self.repository._check()
        if self.path is None:
            url = urljoin(self.repository.url, self.metadata.urls[0])
            return self._unpack(await self.repository._fetch(url, MAX_ARCHIVE_BYTES))
        return self.path

    async def _applier(self, client: Any, options: dict) -> AsyncApplier:
        path = await self.download()
        return AsyncApplier(client, path / "templates", **self._options(options))

    async def render(self, client: Any, **options):
        return (await self._applier(client, options)).render()

    async def plan(self, client: Any, *, operation: str = "apply", **options):
        return (await self._applier(client, options)).plan(operation=operation)

    async def apply(self, client: Any, *, dry_run: bool = False, **options):
        return await (await self._applier(client, options)).apply(dry_run=dry_run)

    async def delete(self, client: Any, *, dry_run: bool = False, **options):
        return await (await self._applier(client, options)).delete(dry_run=dry_run)

    async def aclose(self):
        self.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.close()


__all__ = [
    "Chart",
    "AsyncChart",
    "ChartRepository",
    "AsyncChartRepository",
    "ChartIndex",
    "ChartMetadata",
    "ChartError",
    "branch_repository_url",
]
