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

"""CLI-compatible repository metadata, ordering, source choice, and ownership."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import yaml

from rapyuta_io_sdk_v2.chart import (
    AsyncChartRepository,
    Chart,
    ChartLoadError,
    ChartRepository,
    ChartSource,
    branch_repository_url,
)
from rapyuta_io_sdk_v2.models.chart import ChartEntry, ChartIndex, ChartMetadata
from tests.chart.helpers import acquisition_client, chart_call, repository_response

CALLER_TIMEOUT = 17

FIXTURES = Path(__file__).parent / "fixtures" / "workflows"
CONFIG = yaml.safe_load((FIXTURES / "cases.yaml").read_text())
EXPECTED = yaml.safe_load((FIXTURES / "outputs.yaml").read_text())


def _response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text=yaml.safe_dump(CONFIG["index"]), request=request)


@pytest.mark.parametrize("branch", CONFIG["branches"])
def test_branch_encoding_matches_cli(branch: str) -> None:
    assert branch_repository_url(branch) == EXPECTED["branches"][branch]


def test_lookup_and_listing_match_cli_with_independent_snapshots() -> None:
    with httpx.Client(transport=httpx.MockTransport(_response)) as client:
        repository = ChartRepository(http_client=client)
        assert repository.index_url == EXPECTED["default_index"]
        entries = repository.find_chart("sample")
        assert [entry.version for entry in entries] == [
            entry["version"] for entry in EXPECTED["lookups"]["sample"]["entries"]
        ]
        assert repository.find_chart("sample:1.0.0")[0].urls == (
            "https://charts.example/sample-1.tgz",
        )
        assert [
            [entry.name, entry.version] for entry in repository.list_charts()
        ] == EXPECTED["listing"]
        repository.fetch_index().entries.clear()
        assert repository.find_chart("sample")
        assert not client.is_closed


@pytest.mark.parametrize("selector", ["missing", "sample:9"])
def test_unknown_chart_or_version_is_identifiable(selector: str) -> None:
    with httpx.Client(transport=httpx.MockTransport(_response)) as client:
        with pytest.raises(ChartLoadError) as error:
            ChartRepository(http_client=client).find_chart(selector)
        assert error.value.selector == selector
        assert error.value.stage == "index"


@pytest.mark.parametrize("branch", [None, "", "bug/fix some"])
def test_index_override_and_branch_precedence(branch: str | None) -> None:
    repository = ChartRepository("https://custom.test/index.yaml", branch=branch)
    expected = (
        EXPECTED["branches"][branch] if branch else "https://custom.test/index.yaml"
    )
    assert repository.index_url == expected


@pytest.mark.asyncio
async def test_async_catalog_matches_native_client_and_preserves_policy() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_response), timeout=CALLER_TIMEOUT
    ) as client:
        repository = AsyncChartRepository(http_client=client)
        assert [e.version for e in await repository.find_chart("sample")] == [
            "2",
            "1.0.0",
            "1.0.0",
        ]
        assert client.timeout.read == CALLER_TIMEOUT
        assert not client.is_closed


@pytest.mark.parametrize("status", [404, 500])
def test_failed_index_does_not_include_response_body(status: int) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status, text="private-response", request=request
            )
        )
    ) as client:
        with pytest.raises(ChartLoadError) as error:
            ChartRepository(http_client=client).fetch_index()
        assert "private-response" not in str(error.value)
        assert error.value.stage == "index"


@pytest.mark.parametrize("location", [None, "", "https://custom.test/index.yaml"])
def test_index_url_selection_matches_cli(location: str | None) -> None:
    key = "custom" if location else "empty_override" if location == "" else "default"
    assert ChartRepository(location).index_url == EXPECTED["index_selection"][key]


def test_branch_failure_does_not_try_default_index() -> None:
    requests = []

    def failed(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(404, request=request)

    with (
        httpx.Client(transport=httpx.MockTransport(failed)) as client,
        pytest.raises(ChartLoadError),
    ):
        ChartRepository(branch="bug/fix some", http_client=client).fetch_index()
    assert requests == [EXPECTED["index_selection"]["branch"]]


@pytest.mark.parametrize(
    "content", ["not: [yaml", "entries: []", "[]", "---\n{}\n---\n{}"]
)
def test_invalid_index_shapes_are_rejected(content: str) -> None:
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, text=content, request=request)
            )
        ) as client,
        pytest.raises(ChartLoadError) as error,
    ):
        ChartRepository(http_client=client).fetch_index()
    assert error.value.category == "invalid_index"


def test_invalid_selector_is_rejected_before_http() -> None:
    calls = []

    def response(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _response(request)

    with (
        httpx.Client(transport=httpx.MockTransport(response)) as client,
        pytest.raises(ChartLoadError) as error,
    ):
        ChartRepository(http_client=client).find_chart("sample:1:2")
    assert error.value.category == "invalid_selector"
    assert calls == []


@pytest.mark.asyncio
async def test_both_catalogs_preserve_metadata_and_deep_snapshots(
    chart_loader: object,
) -> None:
    config = copy.deepcopy(CONFIG["index"])
    config["entries"]["sample"][0]["custom"] = {"nested": ["original"]}

    def response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=yaml.safe_dump(config), request=request)

    async with acquisition_client(chart_loader, response) as client:
        kind = (
            ChartRepository
            if chart_loader.chart_type is Chart
            else AsyncChartRepository
        )
        repository = kind(
            "https://custom.test/index.yaml", branch="branch/x", http_client=client
        )
        index = await chart_call(repository, "fetch_index")
        entries = await chart_call(repository, "find_chart", selector="sample")
        listing = await chart_call(repository, "list_charts")
        assert [[entry.name, entry.version] for entry in listing] == EXPECTED["listing"]
        entry = entries[0]
        assert entry.description == "first entry"
        assert entry.created == "2026-01-01T00:00:00Z"
        assert entry.digest == "synthetic-digest"
        entry.custom["nested"].append("changed")
        index.entries.clear()
        fresh = await chart_call(repository, "find_chart", selector="sample:2")
        assert fresh[0].custom == {"nested": ["original"]}
        assert fresh[0].model_dump(exclude={"custom"}) == ChartEntry.model_validate(
            EXPECTED["lookups"]["sample:2"]["entries"][0]
        ).model_dump(exclude={"custom"})
        assert not client.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "network", "status", "malformed"])
async def test_both_catalogs_attribute_index_failures_without_fallback(
    chart_loader: object,
    failure: str,
) -> None:
    calls = []

    def response(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if failure == "timeout":
            msg = "controlled"
            raise httpx.ReadTimeout(msg, request=request)
        if failure == "network":
            msg = "controlled"
            raise httpx.ConnectError(msg, request=request)
        return httpx.Response(
            500 if failure == "status" else 200,
            text="private: [invalid",
            request=request,
        )

    async with acquisition_client(chart_loader, response) as client:
        kind = (
            ChartRepository
            if chart_loader.chart_type is Chart
            else AsyncChartRepository
        )
        repository = kind(branch="feature", http_client=client)
        with pytest.raises(ChartLoadError) as error:
            await chart_call(repository, "fetch_index")
        assert error.value.stage == "index"
        assert error.value.source == repository.index_url
        assert "private" not in str(error.value)
        assert not client.is_closed
    assert calls == [repository.index_url]


@pytest.mark.asyncio
@pytest.mark.parametrize("timestamp", ["2026-99-99", "2026-10-14T25:00:00Z"])
async def test_yaml_constructor_failure_keeps_index_boundary(
    chart_loader: object, timestamp: str
) -> None:
    calls = []

    def response(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text=f"entries: {{}}\ngenerated: {timestamp}\n")

    async with acquisition_client(chart_loader, response) as client:
        kind = (
            ChartRepository
            if chart_loader.chart_type is Chart
            else AsyncChartRepository
        )
        repository = kind(branch="feature", http_client=client)
        with pytest.raises(ChartLoadError) as error:
            await chart_call(repository, "fetch_index")
        assert error.value.stage == "index"
        assert error.value.category == "invalid_index"
        assert error.value.source == repository.index_url
        assert timestamp not in str(error.value)
        assert not client.is_closed
    assert calls == [repository.index_url]


@pytest.mark.asyncio
async def test_explicit_yaml_scalars_keep_index_contract(
    chart_loader: object, yaml_scalar_case: tuple[str, bool]
) -> None:
    content, valid = yaml_scalar_case
    calls = []

    def response(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(
            200,
            text="entries: {}\ngenerated: !!timestamp 2026-10-14T10:00:00Z\n" + content,
        )

    async with acquisition_client(chart_loader, response) as client:
        kind = (
            ChartRepository
            if chart_loader.chart_type is Chart
            else AsyncChartRepository
        )
        repository = kind(branch="feature", http_client=client)
        if valid:
            index = await chart_call(repository, "fetch_index")
            assert index.generated == datetime(2026, 10, 14, 10, tzinfo=UTC)
            extra = index.model_extra["extra"]
            assert extra == {
                "enabled": True,
                "count": 12,
                "fraction": 1.5,
                "text": "café",
            }
            assert type(extra["enabled"]) is bool
            assert type(extra["count"]) is int
            assert type(extra["fraction"]) is float
        else:
            with pytest.raises(ChartLoadError) as error:
                await chart_call(repository, "fetch_index")
            assert error.value.stage == "index"
            assert error.value.category == "invalid_index"
            assert error.value.source == repository.index_url
            assert content not in str(error.value)
        assert not client.is_closed
    assert calls == [repository.index_url]


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["metadata", "index"])
@pytest.mark.parametrize(
    "error_type", [AttributeError, KeyError, IndexError, ValueError]
)
async def test_yaml_handling_preserves_unrelated_model_failures(
    chart_dir: Path,
    chart_loader: object,
    monkeypatch: pytest.MonkeyPatch,
    *,
    boundary: str,
    error_type: type[Exception],
) -> None:
    failure = error_type("unrelated model failure")

    def invalid_model(*_args: object, **_kwargs: object) -> None:
        raise failure

    model = ChartMetadata if boundary == "metadata" else ChartIndex
    monkeypatch.setattr(model, "model_validate", invalid_model)
    async with acquisition_client(
        chart_loader, repository_response(b"unused")
    ) as client:

        async def operation() -> None:
            if boundary == "metadata":
                await chart_loader(ChartSource.from_directory(chart_dir))
            else:
                kind = (
                    ChartRepository
                    if chart_loader.chart_type is Chart
                    else AsyncChartRepository
                )
                await chart_call(kind(http_client=client), "fetch_index")

        with pytest.raises(error_type) as error:
            await operation()
        assert error.value is failure
        assert not client.is_closed


@pytest.mark.asyncio
async def test_redirects_use_caller_policy_without_mutating_it(
    chart_loader: object,
) -> None:
    calls = []

    def response(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/start.yaml":
            return httpx.Response(
                302, headers={"location": "/redirect.yaml"}, request=request
            )
        return _response(request)

    async with acquisition_client(chart_loader, response) as client:
        client.timeout = httpx.Timeout(CALLER_TIMEOUT)
        before = client.follow_redirects
        kind = (
            ChartRepository
            if chart_loader.chart_type is Chart
            else AsyncChartRepository
        )
        repository = kind("https://chart.test/start.yaml", http_client=client)
        assert (await chart_call(repository, "fetch_index")).entries
        assert client.follow_redirects == before
        assert client.timeout.read == CALLER_TIMEOUT
    assert calls == ["/start.yaml", "/redirect.yaml"]
