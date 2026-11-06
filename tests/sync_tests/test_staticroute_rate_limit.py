"""Protect rate limits across model parsing and the actual SDK HTTP boundary."""

import json

import httpx
import pytest
from pydantic import ValidationError

from rapyuta_io_sdk_v2 import (
    AsyncClient,
    Client,
    StaticRoute,
    StaticRouteRateLimit,
    StaticRouteSpec,
)

SPECS = [
    {},
    {"rateLimit": None},
    {"rateLimit": {"average": 100}},
    {"rateLimit": {"average": 100, "period": "1m", "burst": 20}},
    {"rateLimit": {"average": 100, "period": None, "burst": None}},
    {"rateLimit": {"average": 1_000_000, "period": "500ms", "burst": 0}},
]


def manifest(spec):
    return {"kind": "StaticRoute", "metadata": {"name": "limited"}, "spec": spec}


def assert_spec(actual, expected):
    assert {
        k: v for k, v in actual.items() if k not in ("url", "sourceIPRange")
    } == expected


@pytest.mark.parametrize("spec", SPECS)
def test_round_trip(spec):
    route = StaticRoute.model_validate(manifest(spec))
    payload = json.loads(route.model_dump_json(by_alias=True))
    assert_spec(payload["spec"], spec)
    assert StaticRoute.model_validate(payload) == route


def test_python_names_and_public_exports():
    spec = StaticRouteSpec(
        rate_limit=StaticRouteRateLimit(average=100), source_ip_range=[]
    )
    assert spec.model_dump(by_alias=True)["rateLimit"] == {"average": 100}
    assert spec.model_dump()["rate_limit"] == {"average": 100}
    spec.rate_limit = None
    assert spec.model_dump(by_alias=True)["rateLimit"] is None


def test_average_is_required():
    with pytest.raises(ValidationError):
        StaticRouteRateLimit.model_validate({})


@pytest.mark.parametrize("average", [0, -1, 1_000_001, 2**63, True, 1.5, "100"])
def test_invalid_average(average):
    with pytest.raises(ValidationError):
        StaticRouteRateLimit(average=average)


@pytest.mark.parametrize("burst", [-1, 2**63, True, 1.5, "20"])
def test_invalid_burst(burst):
    with pytest.raises(ValidationError):
        StaticRouteRateLimit(average=100, burst=burst)


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("spec", SPECS)
async def test_http_create_read_update(spec, typed, asynchronous):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=manifest(spec))

    transport = httpx.MockTransport(handler)
    client = AsyncClient() if asynchronous else Client()
    original = client.c
    client.c = (
        httpx.AsyncClient(transport=transport)
        if asynchronous
        else httpx.Client(transport=transport)
    )
    body = StaticRoute.model_validate(manifest(spec)) if typed else manifest(spec)
    try:
        for method, kwargs in (
            ("create_staticroute", {"body": body}),
            ("get_staticroute", {"name": "limited"}),
            ("update_staticroute", {"name": "limited", "body": body}),
        ):
            response = getattr(client, method)(**kwargs)
            if asynchronous:
                response = await response
            assert_spec(response.model_dump(by_alias=True)["spec"], spec)
        assert [r.method for r in requests] == ["POST", "GET", "PUT"]
        for request in (requests[0], requests[2]):
            assert_spec(json.loads(request.content)["spec"], spec)
    finally:
        if asynchronous:
            await client.c.aclose()
            await original.aclose()
        else:
            client.c.close()
            original.close()
