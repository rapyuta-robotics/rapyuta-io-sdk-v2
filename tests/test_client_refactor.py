"""Request contract and transport lifecycle checks for both client variants."""

import inspect
import json

import httpx
import pytest
from pydantic import ValidationError

from rapyuta_io_sdk_v2.async_client import AsyncClient
from rapyuta_io_sdk_v2.client import Client
from rapyuta_io_sdk_v2.config import Configuration
from rapyuta_io_sdk_v2.context import RequestContext
from rapyuta_io_sdk_v2.exceptions import (
    BadRequestError,
    PermissionDeniedError,
    UnauthorizedAccessError,
    UnknownError,
)
from rapyuta_io_sdk_v2.models import (
    ConfigTree,
    ConfigTreeKeyUpdate,
    ConfigTreeRevisionCommit,
    Project,
    ProjectOwnership,
)
from rapyuta_io_sdk_v2.transport import serialize_model
from rapyuta_io_sdk_v2.utils import handle_server_errors


def configuration():
    return Configuration(
        load_cli_config=False,
        auth_token="Bearer token",
        organization_guid="org-default",
        project_guid="project-default",
        v2_api_host="https://platform.test",
        rip_host="https://auth.test",
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, BadRequestError),
        (401, UnauthorizedAccessError),
        (403, PermissionDeniedError),
        (418, UnknownError),
    ],
)
@pytest.mark.parametrize("body", [{"error": "failed"}, ["failed"], "failed", None])
def test_errors_preserve_response(status, expected, body):
    response = httpx.Response(
        status, content=json.dumps(body), headers={"Content-Type": "application/json"}
    )
    with pytest.raises(expected) as caught:
        handle_server_errors(response)
    assert caught.value.status_code == status
    assert caught.value.response is response
    assert caught.value.details == body


def test_plain_text_error():
    response = httpx.Response(403, text="Access denied")
    with pytest.raises(PermissionDeniedError, match="Access denied"):
        handle_server_errors(response)


def test_sync_async_signatures_match():
    for name, method in inspect.getmembers(Client, inspect.isfunction):
        if name.startswith("_") or name == "close":
            continue
        counterpart = getattr(AsyncClient, name)
        if name == "paginate":
            # The async method accepts an awaitable page fetcher.
            assert {
                key: value.replace(annotation=inspect.Parameter.empty)
                for key, value in inspect.signature(method).parameters.items()
            } == {
                key: value.replace(annotation=inspect.Parameter.empty)
                for key, value in inspect.signature(counterpart).parameters.items()
            }
            continue
        assert (
            inspect.signature(method).parameters
            == inspect.signature(counterpart).parameters
        ), name
        if name != "paginate":
            assert (
                inspect.signature(method).return_annotation
                == inspect.signature(counterpart).return_annotation
            ), name
        if name not in {"paginate", "set_project", "set_organization"}:
            assert inspect.iscoroutinefunction(counterpart) or inspect.isasyncgenfunction(
                counterpart
            )


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_requests_use_context_aliases_and_one_call(async_mode):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"metadata": {"name": "demo"}, "spec": {}})

    transport_type = httpx.AsyncClient if async_mode else httpx.Client
    external = transport_type(transport=httpx.MockTransport(respond))
    client = (AsyncClient if async_mode else Client)(configuration(), transport=external)
    body = Project(metadata={"name": "demo", "labels": {"userKey": "unchanged"}}, spec={})
    context = RequestContext(
        organization_guid="org-request", headers={"X-Trace": "example"}
    )
    if async_mode:
        result = await client.create_project(body, context=context)
        await client.aclose()
    else:
        result = client.create_project(body, context=context)
        client.close()
    assert isinstance(result, Project)
    assert len(requests) == 1
    assert requests[0].headers["organizationguid"] == "org-request"
    assert requests[0].headers["Authorization"] == "Bearer token"
    assert requests[0].headers["X-Trace"] == "example"
    encoded = json.loads(requests[0].content)
    assert encoded["apiVersion"] == body.api_version
    assert encoded["metadata"]["labels"] == {"userKey": "unchanged"}
    assert not external.is_closed
    if async_mode:
        await external.aclose()
    else:
        external.close()


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_rejects_dictionary_before_request(async_mode):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={})

    cls = httpx.AsyncClient if async_mode else httpx.Client
    external = cls(transport=httpx.MockTransport(respond))
    client = (AsyncClient if async_mode else Client)(configuration(), transport=external)
    with pytest.raises(TypeError, match="Project instance"):
        if async_mode:
            await client.create_project({"metadata": {"name": "demo"}})
        else:
            client.create_project({"metadata": {"name": "demo"}})
    assert not requests
    if async_mode:
        await external.aclose()
    else:
        external.close()


def test_owned_sync_transport_closes():
    with Client(configuration()) as client:
        assert not client.c.is_closed
    assert client.c.is_closed


@pytest.mark.asyncio
async def test_owned_async_transport_closes():
    async with AsyncClient(configuration()) as client:
        assert not client.c.is_closed
    assert client.c.is_closed


@pytest.mark.asyncio
async def test_async_login_uses_injected_async_transport():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"data": {"token": "new-token"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as external:
        async with AsyncClient(configuration(), transport=external) as client:
            await client.login("test@example.test", "password")
            assert client.config.auth_token == "new-token"
            assert len(requests) == 1
            assert str(requests[0].url) == "https://auth.test/user/login"


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_response_validation_failure_is_propagated(async_mode):
    cls = httpx.AsyncClient if async_mode else httpx.Client
    external = cls(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"metadata": {}})
        )
    )
    client = (AsyncClient if async_mode else Client)(configuration(), transport=external)
    with pytest.raises(ValidationError):
        if async_mode:
            await client.get_project("id")
        else:
            client.get_project("id")
    if async_mode:
        await external.aclose()
    else:
        external.close()


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_configtree_commit_and_raw_keys(async_mode):
    requests = []

    def respond(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, text="001: true\n")
        return httpx.Response(200, json={"author": "person"})

    cls = httpx.AsyncClient if async_mode else httpx.Client
    external = cls(transport=httpx.MockTransport(respond))
    client = (AsyncClient if async_mode else Client)(configuration(), transport=external)
    body = ConfigTreeRevisionCommit(author="person", message=None)
    if async_mode:
        await client.commit_revision("tree", "revision", body)
        value = await client.get_key_in_revision("tree", "revision", "key")
    else:
        client.commit_revision("tree", "revision", body)
        value = client.get_key_in_revision("tree", "revision", "key")
    assert json.loads(requests[0].content) == {"author": "person", "message": None}
    assert value == "001: true\n"
    if async_mode:
        await external.aclose()
    else:
        external.close()


def test_root_body_preserves_exact_dictionary_keys():
    body = ConfigTreeKeyUpdate.model_validate({"Camel/Key": {"data": "aA=="}})
    assert serialize_model(body)["Camel/Key"]["data"] == "aA=="
    ownership = ProjectOwnership.model_validate({"email_id": "new-owner@example.test"})
    assert serialize_model(ownership) == {"email_id": "new-owner@example.test"}
    tree = ConfigTree(metadata={"name": "tree"}, keys={"User.Key": {"data": "aA=="}})
    assert "User.Key" in serialize_model(tree)["keys"]
