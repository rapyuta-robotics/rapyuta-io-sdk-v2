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

"""Independent CLI decisions validate Chart recreation and defaults forwarding."""

import warnings
from pathlib import Path

import httpx
import pytest
import yaml

from rapyuta_io_sdk_v2 import (
    ApplierExecutionError,
    ApplierOptions,
    AsyncClient,
    ReadinessOptions,
)
from rapyuta_io_sdk_v2.chart import (
    AsyncChart,
    AsyncChartRepository,
    Chart,
    ChartInputs,
    ChartLoadError,
    ChartRepository,
    ChartSource,
    ChartVersionWarning,
)
from tests.chart.helpers import (
    PlatformRecorder,
    acquisition_client,
    chart_call,
    platform_client,
    repository_response,
)

EXPECTED = yaml.safe_load(
    (Path(__file__).parent / "fixtures/workflows/outputs.yaml").read_text()
)


def test_recreation_preview_follows_cli_phase_order(chart_dir: Path) -> None:
    chart = Chart.load(ChartSource.from_directory(chart_dir))
    chart.apply(dry_run=True, delete_existing=True)
    assert [phase.operation for phase in chart.phase_results] == [
        event["operation"] for event in EXPECTED["recreation"]["preview"]["events"]
    ]


@pytest.mark.asyncio
async def test_async_recreation_matches_cli(chart_dir: Path) -> None:
    chart = await AsyncChart.load(ChartSource.from_directory(chart_dir))
    await chart.apply(dry_run=True, delete_existing=True)
    assert [phase.operation for phase in chart.phase_results] == [
        event["operation"] for event in EXPECTED["recreation"]["preview"]["events"]
    ]


def test_worker_readiness_and_values_forwarding_match_cli(chart_dir: Path) -> None:
    forwarding = EXPECTED["forwarding"]["explicit"]
    values = []
    for position, filename in enumerate(forwarding["values"]):
        path = chart_dir.parent / filename
        path.write_text(yaml.safe_dump({"name": f"version-{position}"}))
        values.append(path)
    chart = Chart.load(
        ChartSource.from_directory(chart_dir),
        inputs=ChartInputs(values=values),
        options=ApplierOptions(
            workers=forwarding["workers"],
            readiness=ReadinessOptions(
                checks=forwarding["retry_count"], interval=forwarding["retry_interval"]
            ),
        ),
    )
    assert chart.apply(dry_run=True).outcomes[0].identity.name == "version-1"
    assert chart.options.workers == forwarding["workers"]
    assert chart.options.readiness.checks == forwarding["retry_count"]
    assert chart.options.readiness.interval == forwarding["retry_interval"]


def test_first_download_location_matches_cli(
    chart_dir: Path, archive_bytes: object
) -> None:
    first = EXPECTED["first_package_url"]
    requested = []
    data = archive_bytes(chart_dir)
    entry = {
        "name": "sample",
        "version": "1.0.0",
        "urls": [first, "https://charts.example/second.tgz"],
    }

    def response(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        content = (
            yaml.safe_dump({"entries": {"sample": [entry]}}).encode()
            if request.url.path.endswith("yaml")
            else data
        )
        return httpx.Response(200, content=content, request=request)

    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        chart = Chart.load(
            ChartSource.from_repository("sample:1.0.0"), http_client=client
        )
    assert requested[-1] == first
    assert chart.entry.urls[0] == first


@pytest.mark.asyncio
@pytest.mark.parametrize("selector", list(EXPECTED["lookups"]))
async def test_all_lookup_metadata_matches_cli_in_both_modes(
    chart_loader: object, selector: str
) -> None:
    async with acquisition_client(chart_loader, _workflow_index_response) as client:
        kind = (
            ChartRepository
            if chart_loader.chart_type is Chart
            else AsyncChartRepository
        )
        repository = kind(http_client=client)
        expected = EXPECTED["lookups"][selector]
        if expected["found"]:
            with warnings.catch_warnings(record=True) as diagnostics:
                entries = await chart_call(repository, "find_chart", selector=selector)
            assert not diagnostics
            assert [
                entry.model_dump(mode="json", by_alias=True, exclude_none=True)
                for entry in entries
            ] == expected["entries"]
        else:
            with pytest.raises(ChartLoadError):
                await chart_call(repository, "find_chart", selector=selector)
        rows = await chart_call(repository, "list_charts")
        assert [[entry.name, entry.version] for entry in rows] == EXPECTED["listing"]


def _workflow_index_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200, text=yaml.safe_dump(WORKFLOW_CONFIG["index"]), request=request
    )


@pytest.mark.asyncio
async def test_unversioned_loading_and_first_location_match_cli(
    chart_dir: Path,
    archive_bytes: object,
    chart_loader: object,
) -> None:
    version = EXPECTED["selection"]["version"]
    (chart_dir / "Chart.yaml").write_text(
        yaml.safe_dump({"name": "sample", "version": version})
    )
    package = archive_bytes(chart_dir)
    requested = []

    def response(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return (
            _workflow_index_response(request)
            if request.url.path.endswith("yaml")
            else httpx.Response(200, content=package, request=request)
        )

    async with acquisition_client(chart_loader, response) as client:
        with pytest.warns(ChartVersionWarning):
            chart = await chart_loader(
                ChartSource.from_repository("sample"), http_client=client
            )
        assert chart.entry.version == version
        assert EXPECTED["selection"]["warned"]
        assert requested[-1] == EXPECTED["lookups"]["sample"]["entries"][0]["urls"][0]
        chart.entry.custom["labels"].append("changed")
        assert chart.entry.custom == {"labels": ["recorded"]}


@pytest.mark.asyncio
@pytest.mark.parametrize("case", list(EXPECTED["recreation"]))
async def test_every_recreation_decision_matches_reference(
    chart_dir: Path,
    chart_loader: object,
    case: str,
) -> None:
    expected = EXPECTED["recreation"][case]
    descriptor = next(
        item for item in WORKFLOW_CONFIG["recreation"] if item["id"] == case
    )
    chart = await chart_loader(
        ChartSource.from_directory(chart_dir),
        options=ApplierOptions(
            workers=3, readiness=ReadinessOptions(checks=4, interval=0)
        ),
    )
    recorder = PlatformRecorder(None)
    async with platform_client(chart_loader, recorder) as client:
        if descriptor["fail_delete"]:
            _fail_delete(client)
            with pytest.raises(ApplierExecutionError):
                await chart_call(chart, "apply", client=client, delete_existing=True)
        else:
            await chart_call(
                chart,
                "apply",
                client=client,
                dry_run=descriptor["dryrun"],
                delete_existing=descriptor["recreate"],
            )
    assert [phase.operation for phase in chart.phase_results] == [
        event["operation"] for event in expected["events"]
    ]
    assert all(phase.dry_run == descriptor["dryrun"] for phase in chart.phase_results)
    assert (
        not any(event[0] == "create" for event in recorder.events)
        if expected["failed"]
        else chart.last_result.successful
    )


def _fail_delete(client: object) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        msg = "controlled CLI-equivalent deletion failure"
        raise RuntimeError(msg)

    async def native(*args: object, **kwargs: object) -> None:
        fail(*args, **kwargs)

    client.delete_role = native if isinstance(client, AsyncClient) else fail


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["branch", "package"])
async def test_reference_acquisition_failure_boundaries_without_fallback(
    chart_loader: object, failure: str
) -> None:
    expected = EXPECTED["failures"][failure]
    requested = []

    def response(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if failure == "branch":
            return httpx.Response(404, request=request)
        entry = {
            "name": "sample",
            "version": "1.0.0",
            "urls": WORKFLOW_CONFIG["failures"]["package_urls"],
        }
        return repository_response(b"unused", entry)(request)

    source = ChartSource.from_repository(
        "sample:1.0.0",
        branch=WORKFLOW_CONFIG["failures"]["branch"] if failure == "branch" else None,
    )
    async with acquisition_client(chart_loader, response) as client:
        with pytest.raises(ChartLoadError) as error:
            await chart_loader(source, http_client=client)
    assert expected["failed"]
    assert error.value.stage == ("index" if failure == "branch" else "download")
    if failure == "branch":
        assert requested == expected["requests"]
    else:
        assert len(requested) == 1
        assert not expected["extracted"]
        assert expected["requests"] == WORKFLOW_CONFIG["failures"]["package_urls"][:1]


WORKFLOW_CONFIG = yaml.safe_load(
    (Path(__file__).parent / "fixtures/workflows/cases.yaml").read_text()
)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", list(EXPECTED["forwarding"]))
async def test_default_explicit_secret_and_preview_forwarding_match_cli(
    chart_dir: Path,
    chart_loader: object,
    case: str,
) -> None:
    reference = EXPECTED["forwarding"][case]
    inputs = _forwarding_inputs(chart_dir, reference)
    options = ApplierOptions(
        workers=reference["workers"],
        readiness=ReadinessOptions(
            checks=reference.get("retry_count", 50),
            interval=reference.get("retry_interval", 6),
        ),
    )
    chart = await chart_loader(
        ChartSource.from_directory(chart_dir), inputs=inputs, options=options
    )
    method = "delete" if case == "delete" else "apply"
    kwargs = {"dry_run": reference["dryrun"]}
    if method == "apply":
        kwargs["delete_existing"] = reference["delete_existing"]
    result = await chart_call(chart, method, **kwargs)
    name = "explicit-1-secret" if case == "explicit" else "viewer-plain"
    assert chart.inspect().resource_identities[0].name == name
    assert result.dry_run == reference["dryrun"]
    assert chart.options.workers == reference["workers"]
    assert [phase.operation for phase in chart.phase_results] == (
        ["delete", "apply"] if reference.get("delete_existing") else [method]
    )


def _forwarding_inputs(root: Path, reference: dict) -> ChartInputs:
    values = []
    if reference["values"] != ["values.yaml"]:
        (root / "values.yaml").write_text("unused: [invalid")
        for index, filename in enumerate(reference["values"]):
            path = root.parent / filename
            path.write_text(yaml.safe_dump({"name": f"explicit-{index}"}))
            values.append(path)
    secrets = []
    for filename in reference["secrets"]:
        path = root.parent / filename
        path.write_text("token: secret\n")
        secrets.append(path)
    (root / "templates/role.yaml").write_text(
        "kind: Role\nmetadata:\n"
        "  name: '{{ name }}-{{ secrets.token | default(\"plain\") }}'\n"
        "spec: {rules: []}\n"
    )
    return ChartInputs(values=values, secrets=secrets)


@pytest.mark.parametrize("choice", list(EXPECTED["index_selection"]))
def test_every_index_choice_matches_reference_in_both_modes(
    chart_loader: object, choice: str
) -> None:
    kwargs = {
        "default": {},
        "custom": {"repository": "https://custom.test/index.yaml"},
        "empty_override": {"repository": ""},
        "branch": {
            "repository": "https://custom.test/index.yaml",
            "branch": "bug/fix some",
        },
        "empty_branch": {"branch": ""},
    }[choice]
    kind = ChartRepository if chart_loader.chart_type is Chart else AsyncChartRepository
    assert kind(**kwargs).index_url == EXPECTED["index_selection"][choice]
