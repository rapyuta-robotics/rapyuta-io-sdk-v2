# Copyright 2026 Rapyuta Robotics

"""Source-backed Parameter wire fixtures, independent of SDK model imports."""

from __future__ import annotations

import base64
import copy
import gzip
import json
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs
from xml.etree import ElementTree as ET

import httpx

if TYPE_CHECKING:
    from pathlib import Path

STAMP = "2026-10-13T00:00:00Z"


def parameter_node(path: str = "tree", **values: object) -> dict[str, Any]:
    """Build a node with the metadata required by the service schema."""
    return {
        "type": "ValueNode",
        "name": path.rsplit("/", 1)[-1],
        "path": "/" + path.partition("/")[2],
        "version": 1,
        "updatedAt": STAMP,
        "userGUID": "user",
        **values,
    }


def parameter_blob(identifier: int = 1, **values: object) -> dict[str, Any]:
    """Build a blob reference with numeric ID and nullable deletion metadata."""
    return {
        "ID": identifier,
        "CreatedAt": STAMP,
        "UpdatedAt": STAMP,
        "DeletedAt": None,
        "checksum": "0" * 32,
        "ownerProject": "project",
        "signedUrl": "",
        "status": "Uploaded",
        **values,
    }


def parameter_association() -> dict[str, Any]:
    """Build the blob service's project/tree association shape."""
    return {
        "ID": 1,
        "CreatedAt": STAMP,
        "UpdatedAt": STAMP,
        "DeletedAt": None,
        "project": "project",
        "blobRefId": 1,
        "application": "paramserver",
        "collection": "tree",
        "subRef": "/file.bin",
    }


class ParameterService:
    """Isolated service retaining actual helper-written trees and blob bytes."""

    def __init__(self) -> None:
        """Initialize empty state and an auditable request history."""
        self.nodes: dict[str, dict[str, Any]] = {}
        self.blobs: dict[int, dict[str, Any]] = {}
        self.content: dict[int, bytes] = {}
        self.blocks: dict[tuple[int, str], bytes] = {}
        self.requests: list[httpx.Request] = []
        self.reject: tuple[str, str, int] | None = None

    def platform(self, request: httpx.Request) -> httpx.Response:
        """Execute only explicitly supported Parameter operations."""
        self.requests.append(request)
        if self.reject and (request.method, request.url.path) == self.reject[:2]:
            return httpx.Response(self.reject[2], json={"error": "injected failure"})
        path = request.url.path.removeprefix("/api/paramserver/")
        if path == "treeblobs":
            return httpx.Response(
                200,
                json={
                    "data": self.blob_listing(request.url.params.get_list("treeNames"))
                },
            )
        if path == "tree":
            return httpx.Response(200, json={"data": self.tree_names()})
        return self._dispatch(request, path)

    def _dispatch(self, request: httpx.Request, path: str) -> httpx.Response:
        if path.startswith("tree/"):
            return self._tree(request, path.removeprefix("tree/"))
        if path.startswith("binaryfilenode/"):
            return self._binary(request, path.removeprefix("binaryfilenode/"))
        message = f"Unexpected platform request: {request.method} {request.url.path}"
        raise AssertionError(message)

    def tree_names(self) -> list[str]:
        """Return only stored root names."""
        return sorted(path for path in self.nodes if "/" not in path)

    def tree(self, path: str) -> dict[str, Any]:
        """Build a recursive service response from helper-created node state."""
        node = copy.deepcopy(self.nodes[path])
        node["children"] = [
            self.tree(child)
            for child in sorted(self.nodes)
            if child.rpartition("/")[0] == path
        ]
        return node

    def blob_listing(self, names: list[str]) -> dict[str, Any]:
        """List only references associated with the requested trees."""
        identifiers = {
            int(node["blobRefId"])
            for path, node in self.nodes.items()
            if path.split("/", 1)[0] in names and node.get("blobRefId")
        }
        refs = [
            copy.deepcopy(self.blobs[identifier]) for identifier in sorted(identifiers)
        ]
        return {
            "isComplete": all(ref["status"] == "Uploaded" for ref in refs),
            "blobRefs": refs,
        }

    def _tree(self, request: httpx.Request, path: str) -> httpx.Response:
        if request.method == "DELETE":
            self.nodes = {
                key: value
                for key, value in self.nodes.items()
                if key != path and not key.startswith(path + "/")
            }
            return httpx.Response(200, json={"data": "ok"})
        if request.method == "GET":
            return httpx.Response(200, json={"data": self.tree(path)})
        if request.method != "PUT":
            raise AssertionError(request.method)
        if path in self.nodes:
            return httpx.Response(400, json={"error": "already exists"})
        payload = json.loads(request.content) if request.content else {}
        self.nodes[path] = parameter_node(path, **payload)
        data = self.nodes[path] if "/" in path else path
        return httpx.Response(201, json={"data": data})

    def _binary(self, request: httpx.Request, path: str) -> httpx.Response:
        if request.method == "PATCH":
            identifier = int(path.rsplit("/", 1)[1])
            if identifier not in self.content:
                return httpx.Response(403, json={"error": "missing content"})
            self.blobs[identifier]["status"] = "Uploaded"
            return httpx.Response(200, json={"data": {"upload": True}})
        checksum = request.headers["checksum"]
        identifier = self._reference(checksum)
        values = {
            "type": "FileNode",
            "blobRefId": str(identifier),
            "checksum": checksum,
            "contentType": request.headers["content-type"],
        }
        if self.blobs[identifier]["status"] != "Uploaded":
            values["uploadUrl"] = f"https://storage/{identifier}?sig=a%2Bb%2Fc&sv=1"
        self.nodes[path] = parameter_node(path, **values)
        return httpx.Response(201, json={"data": self.nodes[path]})

    def _reference(self, checksum: str) -> int:
        identifier = next(
            (key for key, value in self.blobs.items() if value["checksum"] == checksum),
            len(self.blobs) + 1,
        )
        if identifier not in self.blobs:
            self.blobs[identifier] = parameter_blob(
                identifier,
                checksum=checksum,
                status="Pending",
                signedUrl=f"https://storage/{identifier}?sig=download",
            )
        return identifier

    def storage(self, request: httpx.Request) -> httpx.Response:
        """Capture Azure block transfers without allowing any real network I/O."""
        self.requests.append(request)
        identifier = int(request.url.path.lstrip("/"))
        query = parse_qs(request.url.query.decode())
        operation = query.get("comp", [""])[0]
        if operation == "block":
            block = query["blockid"][0]
            base64.b64decode(block, validate=True)
            self.blocks[identifier, block] = request.content
        elif operation == "blocklist":
            # XML is produced by the isolated adapter, never a remote input.
            root = ET.fromstring(request.content)  # noqa: S314
            ids = [child.text for child in root]
            self.content[identifier] = b"".join(
                self.blocks[identifier, block] for block in ids
            )
        else:
            self.content[identifier] = request.content
        return httpx.Response(201)


def signed_query_error(
    service: ParameterService, request: httpx.Request, *, scenario: str, scheme: str
) -> httpx.Response:
    """Inject signed URLs into platform and validation error context."""
    response = service.platform(request)
    url = f"{scheme}://storage/blob?sig=fake-secret"
    if scenario == "verification":
        return verification_error(request, response, url)
    if "/binaryfilenode/" not in request.url.path:
        return response
    if scenario == "platform":
        return httpx.Response(500, json={"error": f"Cannot sign {url}"})
    payload = response.json()
    payload["data"]["blobRefId"] = url
    return httpx.Response(201, json=payload)


def verification_error(
    request: httpx.Request, response: httpx.Response, url: str
) -> httpx.Response:
    """Fail verification after the known ambiguous commit response."""
    if request.method == "PATCH":
        return httpx.Response(
            403,
            json={
                "error": "blobRef signed url not generated or blobRef already uploaded"
            },
        )
    if request.url.path.endswith("/treeblobs"):
        return httpx.Response(500, json={"error": f"Cannot verify {url}"})
    return response


def media_source(root: Path, *, filename: str, size: int) -> bytes:
    """Write a plain file or real gzip stream without compressing test blocks."""
    tree = root / "tree"
    tree.mkdir()
    payload = b"z" * size
    if filename.endswith(".gz"):
        payload = gzip.compress(payload, compresslevel=0, mtime=0)
    (tree / filename).write_bytes(payload)
    return payload


def check_media_headers(
    preparation: httpx.Request, storage: httpx.Request, encoding: str | None
) -> None:
    """Require MIME/encoding on preparation and stored blob properties."""
    assert preparation.headers["content-type"] == "text/plain"
    assert preparation.headers.get("content-encoding") == encoding
    assert storage.headers["x-ms-blob-content-type"] == "text/plain"
    assert storage.headers.get("x-ms-blob-content-encoding") == encoding
