# Copyright 2026 Rapyuta Robotics

"""Isolated synchronous and asynchronous Azure Block Blob transfers."""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol
from urllib.parse import urlencode, urlsplit
from xml.etree import ElementTree as ET

import httpx

from rapyuta_io_sdk_v2.helpers._parameter_source import (
    BLOCK_SIZE,
    check_source,
    read_chunk,
)
from rapyuta_io_sdk_v2.helpers._parameter_upload import disk_work

if TYPE_CHECKING:
    from rapyuta_io_sdk_v2.helpers._parameter_source import ClassifiedFile


class _Digest(Protocol):
    def update(self, data: bytes) -> None: ...
    def hexdigest(self) -> str: ...


def _md5(data: bytes) -> str:
    return base64.b64encode(hashlib.md5(data, usedforsecurity=False).digest()).decode()


def _operation_url(url: str, **params: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        message = "Invalid signed storage URL"
        raise ValueError(message)
    if parsed.username or parsed.fragment:
        message = "Invalid signed storage URL"
        raise ValueError(message)
    separator = "&" if "?" in url else "?"
    return url + (separator + urlencode(params) if params else "")


def _request(url: str, content: bytes, headers: dict[str, str]) -> httpx.Request:
    return httpx.Request(
        "PUT",
        url,
        content=content,
        headers={
            "x-ms-version": "2021-12-02",
            "Content-Length": str(len(content)),
            **headers,
        },
    )


def _properties(source: ClassifiedFile) -> dict[str, str]:
    headers = {
        "x-ms-blob-content-type": source.content_type,
        "x-ms-blob-content-md5": base64.b64encode(
            bytes.fromhex(source.checksum)
        ).decode(),
    }
    if source.content_encoding is not None:
        headers["x-ms-blob-content-encoding"] = source.content_encoding
    return headers


def _accepted(response: httpx.Response) -> None:
    if response.status_code != httpx.codes.CREATED:
        message = f"Storage returned status {response.status_code}"
        raise httpx.HTTPStatusError(
            message, request=response.request, response=response
        )


@dataclass
class _Transfer:
    source: ClassifiedFile
    url: str
    prefix: str = field(default_factory=lambda: secrets.token_hex(16))
    ids: list[str] = field(default_factory=list)
    digest: _Digest = field(default_factory=lambda: hashlib.md5(usedforsecurity=False))
    size: int = 0

    def chunk(self, content: bytes) -> httpx.Request:
        self.digest.update(content)
        self.size += len(content)
        if self.source.entry.identity.st_size <= BLOCK_SIZE:
            headers = {"x-ms-blob-type": "BlockBlob", **_properties(self.source)}
            return _request(_operation_url(self.url), content, headers)
        identifier = base64.b64encode(
            f"{self.prefix}:{len(self.ids):05d}".encode()
        ).decode()
        self.ids.append(identifier)
        return _request(
            _operation_url(self.url, comp="block", blockid=identifier),
            content,
            {"Content-MD5": _md5(content)},
        )

    def verify(self) -> None:
        check_source(self.source.entry)
        if (
            self.size != self.source.entry.identity.st_size
            or self.digest.hexdigest() != self.source.checksum
        ):
            message = "Source checksum changed during storage transfer"
            raise ValueError(message)

    def commit(self) -> httpx.Request:
        root = ET.Element("BlockList")
        for identifier in self.ids:
            ET.SubElement(root, "Latest").text = identifier
        content = ET.tostring(root, encoding="utf-8")
        return _request(
            _operation_url(self.url, comp="blocklist"),
            content,
            {"Content-Type": "application/xml", **_properties(self.source)},
        )


def transfer_blob(client: httpx.Client, url: str, source: ClassifiedFile) -> None:
    """Transfer bounded blocks, verify original bytes, then finalize storage."""
    state = _Transfer(source, url)
    for offset in range(0, max(source.entry.identity.st_size, 1), BLOCK_SIZE):
        content = read_chunk(source.entry, offset)
        request = state.chunk(content)
        _accepted(client.send(request, auth=None, follow_redirects=False))
        del request, content
    state.verify()
    if state.ids:
        _accepted(client.send(state.commit(), auth=None, follow_redirects=False))
    check_source(source.entry)


async def transfer_blob_async(
    client: httpx.AsyncClient, url: str, source: ClassifiedFile
) -> None:
    """Await each storage operation and offload worker-owned bounded reads."""
    state = _Transfer(source, url)
    for offset in range(0, max(source.entry.identity.st_size, 1), BLOCK_SIZE):
        content = await disk_work(read_chunk, source.entry, offset)
        request = await disk_work(state.chunk, content)
        _accepted(await client.send(request, auth=None, follow_redirects=False))
        del request, content
    await disk_work(state.verify)
    if state.ids:
        request = await disk_work(state.commit)
        _accepted(await client.send(request, auth=None, follow_redirects=False))
    await disk_work(check_source, source.entry)
