# Copyright 2026 Rapyuta Robotics

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest
from pydantic import ValidationError as ModelValidationError

from rapyuta_io_sdk_v2 import Client, Configuration
from rapyuta_io_sdk_v2.exceptions import (
    HttpAlreadyExistsError,
    HttpNotFoundError,
    InternalServerError,
    MethodNotAllowedError,
    UnauthorizedAccessError,
    UnknownError,
    ValidationError,
)
from rapyuta_io_sdk_v2.models.parameter import (
    ParameterBlobQuery,
    ParameterNodeDelete,
    ParameterNodeWrite,
    ParameterTreeQuery,
    ParameterUploadMetadata,
)
from tests.data.parameter_data import parameter_node

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def target() -> Iterator[Client]:
    instance = Client(
        Configuration(
            auth_token="token", project_guid="project", core_api_host="https://core"
        )
    )
    instance.c.close()
    yield instance
    instance.c.close()


CASES = [
    (
        "list_parameter_trees",
        (),
        {"query": ParameterTreeQuery(instances=("a.*", "b.*"))},
        "GET",
        "/tree",
        {"data": ["tree"]},
    ),
    ("create_parameter_tree", ("tree",), {}, "PUT", "/tree/tree", {"data": "tree"}),
    (
        "get_parameter_tree",
        ("tree",),
        {},
        "GET",
        "/tree/tree",
        {"data": parameter_node()},
    ),
    (
        "put_parameter_node",
        ("tree/folder", ParameterNodeWrite(node_type="FolderNode", version=4)),
        {},
        "PUT",
        "/tree/tree/folder",
        {"data": parameter_node("tree/folder", type="FolderNode")},
    ),
    ("delete_parameter_tree", ("tree",), {}, "DELETE", "/tree/tree", {"data": "ok"}),
    (
        "delete_parameter_node",
        ("tree/folder", ParameterNodeDelete(node_type="FolderNode", version=4)),
        {},
        "DELETE",
        "/tree/tree/folder",
        {"data": "ok"},
    ),
    (
        "list_parameter_blobs",
        (ParameterBlobQuery(tree_names=("tree", "other")),),
        {},
        "GET",
        "/treeblobs",
        {"data": {"isComplete": True, "blobRefs": []}},
    ),
    (
        "prepare_parameter_upload",
        (
            "tree/file.bin",
            ParameterUploadMetadata(
                checksum="0" * 32, content_type="application/octet-stream", version=7
            ),
        ),
        {},
        "PUT",
        "/binaryfilenode/tree/file.bin",
        {"data": parameter_node("tree/file.bin", type="FileNode", blobRefId="1")},
    ),
    (
        "commit_parameter_upload",
        ("tree", "1"),
        {},
        "PATCH",
        "/binaryfilenode/tree/blobref/1",
        {"data": {"upload": True}},
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case[0])
def test_each_operation_issues_one_request(target: Client, case: tuple) -> None:
    name, args, kwargs, verb, path, payload = case
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    target.c = httpx.Client(transport=httpx.MockTransport(respond))
    result = getattr(target, name)(*args, **kwargs, project_guid="override")
    assert result.data is not None
    assert len(requests) == 1
    request = requests[0]
    assert request.method == verb
    assert request.url.path == "/api/paramserver" + path
    assert request.headers["project"] == "override"
    assert request.headers["authorization"] == "Bearer token"
    assert request.url.host == "core"
    check_payload(name, request)


def check_payload(name: str, request: httpx.Request) -> None:
    if name in {"put_parameter_node", "delete_parameter_node"}:
        assert json.loads(request.content) == {"type": "FolderNode", "version": 4}
    else:
        assert request.content == b""
    if name == "list_parameter_trees":
        assert request.url.params.get_list("instances") == ["a.*", "b.*"]
    if name == "list_parameter_blobs":
        assert request.url.params.get_list("treeNames") == ["tree", "other"]
    if name == "prepare_parameter_upload":
        assert request.headers["checksum"] == "0" * 32
        assert request.headers["x-rapyuta-params-version"] == "7"
        assert "x-checksum" not in request.headers


@pytest.mark.parametrize(
    "case",
    [
        (400, MethodNotAllowedError),
        (403, MethodNotAllowedError),
        (401, UnauthorizedAccessError),
        (404, HttpNotFoundError),
        (409, HttpAlreadyExistsError),
        (302, UnknownError),
    ],
)
def test_operation_error_mapping(
    target: Client, case: tuple[int, type[Exception]]
) -> None:
    status, error = case
    target.c = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(status, json={"error": "rejected"})
        )
    )
    with pytest.raises(error):
        target.get_parameter_tree("tree")


@pytest.mark.parametrize(
    "payload", [None, {}, {"data": None}, {"error": "oops"}, {"data": 1}]
)
def test_malformed_success(target: Client, payload: object) -> None:
    target.c = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    )
    with pytest.raises((ModelValidationError, UnknownError)):
        target.get_parameter_tree("tree")


@pytest.mark.parametrize(
    "path",
    ["/tree/file", "tree//file", "tree/../file", "tree/./file", "tree\\file", "tree"],
)
def test_invalid_child_paths_before_io(target: Client, path: str) -> None:
    with pytest.raises(ValidationError):
        target.put_parameter_node(path, ParameterNodeWrite(node_type="FolderNode"))


def test_environment_resolved_at_call_time(target: Client) -> None:
    target.config.core_api_host = None
    target.config.set_environment("dev")
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": []})

    target.c = httpx.Client(transport=httpx.MockTransport(respond))
    target.list_parameter_trees()
    assert requests[0].url.host.startswith("devapiserver")
    target.config.set_environment("local")
    with pytest.raises(ValidationError):
        target.list_parameter_trees()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case[0])
def test_redirect_enabled_transport_still_issues_one_request(
    target: Client, case: tuple
) -> None:
    name, args, kwargs, verb, path, payload = case
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(307, headers={"location": "/redirect-target"})
        return httpx.Response(200, json=payload)

    target.c = httpx.Client(
        transport=httpx.MockTransport(respond), follow_redirects=True
    )
    with pytest.raises(UnknownError, match="Unexpected Parameter status: 307"):
        getattr(target, name)(*args, **kwargs)
    assert len(requests) == 1
    assert requests[0].method == verb
    assert requests[0].url.path == "/api/paramserver" + path


@pytest.mark.parametrize("kind", ["trees", "blobs"])
@pytest.mark.parametrize("construction", ["mutated", "constructed"])
def test_query_serializes_revalidated_values(
    target: Client, kind: str, construction: str
) -> None:
    query_type = ParameterTreeQuery if kind == "trees" else ParameterBlobQuery
    field = "instances" if kind == "trees" else "tree_names"
    alias = "instances" if kind == "trees" else "treeNames"
    values = (b"normalized", b"other", b"normalized")
    query = query_type(**{field: ("initial",)})
    if construction == "mutated":
        setattr(query, field, values)
    else:
        query = query_type.model_construct(**{field: values})
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        data = [] if kind == "trees" else {"isComplete": True, "blobRefs": []}
        return httpx.Response(200, json={"data": data})

    target.c = httpx.Client(transport=httpx.MockTransport(respond))
    method = (
        target.list_parameter_trees if kind == "trees" else target.list_parameter_blobs
    )
    with pytest.warns(UserWarning, match="Pydantic serializer warnings"):
        method(query=query)
    assert len(requests) == 1
    assert requests[0].url.params.multi_items() == [
        (alias, "normalized"),
        (alias, "other"),
        (alias, "normalized"),
    ]


@pytest.mark.parametrize(
    "body",
    [
        b'{"data":"tree","error":"rejected"}',
        rb'{"data":"tree","err\u006fr":"rejected"}',
    ],
)
def test_success_status_error_envelope(target: Client, body: bytes) -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, content=body)

    target.c = httpx.Client(transport=httpx.MockTransport(respond))
    with pytest.raises(UnknownError, match="rejected"):
        target.create_parameter_tree("tree")
    assert len(requests) == 1


@pytest.mark.parametrize("body", [b"invalid JSON", b'{"data":', b"\xff"])
def test_malformed_success_json(target: Client, body: bytes) -> None:
    target.c = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(201, content=body))
    )
    with pytest.raises(ModelValidationError):
        target.create_parameter_tree("tree")


@pytest.mark.parametrize(
    "case",
    [
        (400, MethodNotAllowedError),
        (401, UnauthorizedAccessError),
        (403, MethodNotAllowedError),
        (404, HttpNotFoundError),
        (409, HttpAlreadyExistsError),
        (500, InternalServerError),
    ],
)
def test_non_utf8_error_preserves_mapping(
    target: Client, case: tuple[int, type[Exception]]
) -> None:
    status, error_type = case
    target.c = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(status, content=b"\xffproxy error")
        )
    )
    with pytest.raises(error_type, match="proxy error") as caught:
        target.get_parameter_tree("tree")
    assert caught.value.status_code == status


@pytest.mark.parametrize("case", CASES, ids=lambda case: case[0])
@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ReadTimeout])
def test_transport_failure_preserves_original_error(
    target: Client, case: tuple, error_type: type[httpx.TransportError]
) -> None:
    name, args, kwargs, verb, path, _ = case
    requests = []
    error = error_type("injected transport failure")

    def fail(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise error

    target.c = httpx.Client(transport=httpx.MockTransport(fail))
    with pytest.raises(error_type) as caught:
        getattr(target, name)(*args, **kwargs)
    assert caught.value is error
    assert len(requests) == 1
    assert caught.value.request is requests[0]
    assert requests[0].method == verb
    assert requests[0].url.path == "/api/paramserver" + path


@pytest.mark.parametrize(
    "case",
    [
        case
        for case in CASES
        if case[0]
        in {"put_parameter_node", "delete_parameter_node", "prepare_parameter_upload"}
    ],
    ids=lambda case: case[0],
)
@pytest.mark.parametrize("status", [400, 409])
def test_version_conflict_preserves_supplied_version(
    target: Client, case: tuple, status: int
) -> None:
    name, args, kwargs, verb, path, _ = case
    requests = []

    def conflict(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, json={"error": "version conflict"})

    target.c = httpx.Client(transport=httpx.MockTransport(conflict))
    error_type = (
        MethodNotAllowedError
        if status == httpx.codes.BAD_REQUEST
        else HttpAlreadyExistsError
    )
    with pytest.raises(error_type, match=r"^version conflict$") as caught:
        getattr(target, name)(*args, **kwargs)
    assert caught.value.status_code == status
    assert len(requests) == 1
    assert requests[0].method == verb
    assert requests[0].url.path == "/api/paramserver" + path
    check_payload(name, requests[0])


@pytest.mark.parametrize("encoding", [None, "gzip"])
def test_preparation_metadata_overrides_generic_headers(
    target: Client, encoding: str | None
) -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            201,
            json={
                "data": parameter_node(
                    "tree/file.txt.gz", type="FileNode", blobRefId="1"
                )
            },
        )

    target.c = httpx.Client(transport=httpx.MockTransport(respond))
    metadata = ParameterUploadMetadata(
        version=7,
        checksum="a" * 32,
        content_type="text/plain",
        content_encoding=encoding,
    )
    target.prepare_parameter_upload(
        "tree/file.txt.gz",
        metadata,
        content_type="application/json",
        x_checksum="b" * 32,
    )
    assert len(requests) == 1
    assert requests[0].content == b""
    assert requests[0].headers["content-type"] == "text/plain"
    assert requests[0].headers["checksum"] == "a" * 32
    assert requests[0].headers["x-rapyuta-params-version"] == "7"
    assert requests[0].headers.get("content-encoding") == encoding
    assert "x-checksum" not in requests[0].headers
