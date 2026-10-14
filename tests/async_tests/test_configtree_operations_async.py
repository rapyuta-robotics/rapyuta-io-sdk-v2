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

"""Asynchronous parity and cancellation checks for configuration trees."""

import asyncio
from pathlib import Path

import httpx
import pytest

from rapyuta_io_sdk_v2 import AsyncClient, Configuration
from rapyuta_io_sdk_v2.configtree import (
    AsyncRevision,
    ConfigTreeInputError,
    ConfigTreeMergeConflictError,
    ConfigTreeMutationError,
    ConfigTreeReferenceError,
    ImportOptions,
    RevisionOptions,
    import_configtree_async,
    merge_configtree_async,
)
from rapyuta_io_sdk_v2.configtree._values import encode_value
from rapyuta_io_sdk_v2.exceptions import ServiceUnavailableError
from tests.utils.configtree_operations import ConfigtreeTransport


@pytest.fixture
def platform() -> ConfigtreeTransport:
    state = ConfigtreeTransport()
    state.add_tree(
        "proj",
        "target",
        head="rev-target",
        keys={
            "existing": encode_value("old").model_dump(
                by_alias=True, exclude_unset=True
            )
        },
    )
    state.add_tree(
        "org",
        "source",
        head="rev-source",
        keys={
            "added": encode_value("new").model_dump(by_alias=True, exclude_unset=True)
        },
    )
    return state


@pytest.fixture
def sdk(platform: ConfigtreeTransport) -> AsyncClient:
    client = AsyncClient(
        Configuration(
            organization_guid="org-id",
            project_guid="project-id",
            v2_api_host="https://example.test",
        )
    )
    client.c = httpx.AsyncClient(transport=httpx.MockTransport(platform))
    return client


@pytest.mark.asyncio
async def test_async_revision_edit_and_empty(
    sdk: AsyncClient,
    platform: ConfigtreeTransport,
) -> None:
    async with AsyncRevision(
        sdk, "target", options=RevisionOptions(commit=True)
    ) as revision:
        pending = revision.keys
        revision.store("x", "one")
        revision.store("y", "two")
        del pending["y"]
    assert [s for s, _, _ in platform.calls] == ["create", "store", "commit"]
    assert revision.keys is pending
    assert "x" in platform.revisions[("proj", "target", revision.revision_id)]["keys"]


@pytest.mark.asyncio
async def test_async_unsuccessful_batch_stops_commit(
    sdk: AsyncClient, platform: ConfigtreeTransport
) -> None:
    platform.batch_response = {"error": "rejected"}
    revision = AsyncRevision(sdk, "target", options=RevisionOptions(commit=True))

    async def unsuccessful() -> None:
        async with revision:
            revision.store("key", "value")

    with pytest.raises(ConfigTreeMutationError) as captured:
        await unsuccessful()
    assert captured.value.configtree_stage == "store"
    assert captured.value.configtree_revision_id == revision.revision_id
    assert [stage for stage, _, _ in platform.calls] == ["create", "store"]


@pytest.mark.asyncio
@pytest.mark.parametrize("batch_response", [{}, {"success": None}])
async def test_async_batch_requires_affirmative_acknowledgement(
    sdk: AsyncClient, platform: ConfigtreeTransport, batch_response: dict
) -> None:
    platform.batch_response = batch_response
    revision = AsyncRevision(sdk, "target", options=RevisionOptions(commit=True))

    with pytest.raises(ConfigTreeMutationError) as captured:
        async with revision:
            revision.store("key", "value")

    assert captured.value.configtree_stage == "store"
    assert captured.value.configtree_revision_id == revision.revision_id
    assert [stage for stage, _, _ in platform.calls] == ["create", "store"]


@pytest.mark.asyncio
async def test_async_batch_uses_snapshot_before_await(
    sdk: AsyncClient, platform: ConfigtreeTransport
) -> None:
    revision = AsyncRevision(sdk, "target")

    async def handler(request: httpx.Request) -> httpx.Response:
        parts = [part for part in request.url.path.split("/") if part]
        if platform.stage_for_request(request.method, parts) == "store":
            revision.keys["key"].metadata = {"late": "change"}
        return platform(request)

    sdk.c = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with revision:
        revision.store("key", "value", metadata={})
    stored = platform.revisions[("proj", "target", revision.revision_id)]["keys"]
    assert stored["key"]["metadata"] == {}


@pytest.mark.asyncio
async def test_async_empty_and_invalid_pending_maps(
    sdk: AsyncClient, platform: ConfigtreeTransport
) -> None:
    async with AsyncRevision(sdk, "target") as empty:
        empty.store("removed", 1)
        empty.keys.clear()
    assert [stage for stage, _, _ in platform.calls] == ["create"]
    invalid = AsyncRevision(sdk, "target", options=RevisionOptions(commit=True))

    async def invalid_context() -> None:
        async with invalid:
            invalid.store("bad", "value")
            invalid.keys["bad"].checksum = "stale"

    with pytest.raises(ConfigTreeInputError) as captured:
        await invalid_context()
    assert captured.value.configtree_stage == "validate"
    assert [stage for stage, _, _ in platform.calls] == ["create", "create"]


@pytest.mark.asyncio
async def test_async_import_merge(
    sdk: AsyncClient, platform: ConfigtreeTransport, tmp_path: Path
) -> None:
    path = tmp_path / "robot.yaml"
    path.write_text("speed: {value: 2, metadata: {unit: m/s}}\n")
    imported = await import_configtree_async(
        sdk, "target", [path], options=ImportOptions(commit=True, update_head=True)
    )
    assert platform.trees[("proj", "target")]["head"]["metadata"]["guid"] == imported
    merged = await merge_configtree_async(sdk, "target", "org/source")
    assert set(platform.revisions[("proj", "target", merged)]["keys"]) == {
        "robot/speed",
        "existing",
        "added",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("commit", [False, True])
@pytest.mark.parametrize("update_head", [False, True])
async def test_async_import_publication_options(
    sdk: AsyncClient,
    platform: ConfigtreeTransport,
    tmp_path: Path,
    *,
    commit: bool,
    update_head: bool,
) -> None:
    path = tmp_path / "robot.json"
    path.write_text('{"name":"東京"}')
    revision_id = await import_configtree_async(
        sdk,
        "target",
        [path],
        options=ImportOptions(commit=commit, update_head=update_head),
    )
    assert platform.revisions[("proj", "target", revision_id)]["committed"] is commit
    assert platform.trees[("proj", "target")]["head"]["metadata"]["guid"] == (
        revision_id if update_head else "rev-target"
    )
    assert [stage for stage, _, _ in platform.calls] == [
        "get",
        "create",
        "store",
        *(["commit"] if commit else []),
        *(["head"] if update_head else []),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["org", "proj"])
@pytest.mark.parametrize("selector", ["", "/rev-source", "/release"])
async def test_async_merge_refspec_forms(
    sdk: AsyncClient,
    platform: ConfigtreeTransport,
    *,
    scope: str,
    selector: str,
) -> None:
    platform.add_tree(
        "proj",
        "source",
        head="rev-source",
        keys={
            "added": encode_value("new").model_dump(by_alias=True, exclude_unset=True)
        },
    )
    platform.revisions[(scope, "source", "rev-source")]["metadata"]["labels"] = {
        "rapyuta.io/milestone": "release"
    }
    platform.page_size = 1
    revision_id = await merge_configtree_async(
        sdk, "target", f"{scope}/source{selector}"
    )
    assert "added" in platform.revisions[("proj", "target", revision_id)]["keys"]
    assert platform.trees[(scope, "source")]["head"]["metadata"]["guid"] == "rev-source"


@pytest.mark.asyncio
async def test_async_merge_conflict_and_bad_source_length(
    sdk: AsyncClient, platform: ConfigtreeTransport
) -> None:
    source_keys = platform.revisions[("org", "source", "rev-source")]["keys"]
    source_keys["existing"] = encode_value("different").model_dump(
        by_alias=True, exclude_unset=True
    )
    with pytest.raises(ConfigTreeMergeConflictError):
        await merge_configtree_async(sdk, "target", "org/source")
    assert [stage for stage, _, _ in platform.calls] == ["get", "get"]
    platform.calls.clear()
    del source_keys["existing"]
    source_keys["added"]["contentLength"] = 1
    with pytest.raises(ConfigTreeInputError) as captured:
        await merge_configtree_async(sdk, "target", "org/source")
    assert captured.value.key == "added"
    assert [stage for stage, _, _ in platform.calls] == ["get", "get"]


@pytest.mark.asyncio
async def test_async_empty_union_creates_and_publishes(
    sdk: AsyncClient, platform: ConfigtreeTransport
) -> None:
    platform.add_tree("proj", "empty", head="rev-empty")
    platform.add_tree("org", "blank", head="rev-blank")
    revision_id = await merge_configtree_async(sdk, "empty", "org/blank")
    assert platform.revisions[("proj", "empty", revision_id)]["keys"] == {}
    assert platform.trees[("proj", "empty")]["head"]["metadata"]["guid"] == revision_id
    assert [stage for stage, _, _ in platform.calls] == [
        "get",
        "get",
        "create",
        "commit",
        "head",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_scope", ["proj", "org"])
async def test_async_merge_rejects_omitted_key_map_before_create(
    sdk: AsyncClient, platform: ConfigtreeTransport, missing_scope: str
) -> None:
    missing_name = "target" if missing_scope == "proj" else "source"
    platform.omit_key_maps.add((missing_scope, missing_name))

    with pytest.raises(
        ConfigTreeReferenceError, match="Selected configuration key map is missing"
    ) as captured:
        await merge_configtree_async(sdk, "target", "org/source")

    assert captured.value.configtree_stage == "resolve"
    assert [stage for stage, _, _ in platform.calls] == [
        "get",
        *(["get"] if missing_scope == "org" else []),
    ]
    assert platform.trees[("proj", "target")]["head"]["metadata"]["guid"] == (
        "rev-target"
    )


@pytest.mark.asyncio
async def test_async_merge_unacknowledged_batch_does_not_commit_or_select_head(
    sdk: AsyncClient, platform: ConfigtreeTransport
) -> None:
    platform.batch_response = {"success": None}

    with pytest.raises(ConfigTreeMutationError) as captured:
        await merge_configtree_async(sdk, "target", "org/source")

    assert captured.value.configtree_stage == "store"
    assert [stage for stage, _, _ in platform.calls] == [
        "get",
        "get",
        "create",
        "store",
    ]
    assert platform.trees[("proj", "target")]["head"]["metadata"]["guid"] == (
        "rev-target"
    )


@pytest.mark.asyncio
async def test_async_milestone_mismatch_and_ambiguity(
    sdk: AsyncClient, platform: ConfigtreeTransport
) -> None:
    with pytest.raises(ConfigTreeReferenceError):
        await merge_configtree_async(sdk, "target", "org/source/release")
    assert [stage for stage, _, _ in platform.calls] == ["get", "list"]
    platform.calls.clear()
    platform.page_size = 1
    platform.revisions[("org", "source", "rev-source")]["metadata"]["labels"] = {
        "rapyuta.io/milestone": "release"
    }
    platform.revisions[("org", "source", "rev-extra")] = {
        "metadata": {
            "guid": "rev-extra",
            "labels": {"rapyuta.io/milestone": "release"},
        },
        "committed": True,
        "keys": {},
    }
    with pytest.raises(ConfigTreeReferenceError):
        await merge_configtree_async(sdk, "target", "org/source/release")
    assert [stage for stage, _, _ in platform.calls] == ["get", "list", "list"]


@pytest.mark.asyncio
async def test_body_cancellation_retains_id(
    sdk: AsyncClient, platform: ConfigtreeTransport
) -> None:
    with pytest.raises(asyncio.CancelledError) as captured:
        async with AsyncRevision(sdk, "target") as revision:
            raise asyncio.CancelledError
    assert captured.value.configtree_revision_id == revision.revision_id
    assert captured.value.configtree_stage == "body"
    assert [s for s, _, _ in platform.calls] == ["create"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["create", "store", "commit", "head"])
async def test_async_cancellation_stops_publication(
    sdk: AsyncClient,
    platform: ConfigtreeTransport,
    tmp_path: Path,
    *,
    stage: str,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        parts = [part for part in request.url.path.split("/") if part]
        request_stage = platform.stage_for_request(request.method, parts)
        if request_stage == stage:
            scope = "proj" if "project" in request.headers else "org"
            platform.calls.append((stage, scope, parts[2]))
            raise asyncio.CancelledError
        return platform(request)

    sdk.c = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    path = tmp_path / "robot.json"
    path.write_text('{"key":1}')
    with pytest.raises(asyncio.CancelledError) as captured:
        await import_configtree_async(
            sdk, "target", [path], options=ImportOptions(commit=True, update_head=True)
        )
    assert captured.value.configtree_stage == stage
    if stage != "create":
        assert captured.value.configtree_revision_id == "rev-new-1"
    assert [s for s, _, _ in platform.calls][-1] == stage


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["create", "store", "commit", "head"])
async def test_async_http_failure_stops_publication(
    sdk: AsyncClient,
    platform: ConfigtreeTransport,
    tmp_path: Path,
    *,
    stage: str,
) -> None:
    platform.fail_stage = stage
    path = tmp_path / "robot.json"
    path.write_text('{"key":1}')
    with pytest.raises(ServiceUnavailableError) as captured:
        await import_configtree_async(
            sdk, "target", [path], options=ImportOptions(commit=True, update_head=True)
        )
    assert captured.value.configtree_stage == stage
    if stage != "create":
        assert captured.value.configtree_revision_id == "rev-new-1"
    assert [s for s, _, _ in platform.calls][-1] == stage
