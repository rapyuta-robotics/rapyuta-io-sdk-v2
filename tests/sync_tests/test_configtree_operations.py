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

"""Synchronous workflow and live revision contract checks."""

import base64
from pathlib import Path

import httpx
import pytest

from rapyuta_io_sdk_v2 import Client, Configuration
from rapyuta_io_sdk_v2.configtree import (
    ConfigTreeInputError,
    ConfigTreeMergeConflictError,
    ConfigTreeMutationError,
    ConfigTreeReferenceError,
    ImportOptions,
    MergeOptions,
    Revision,
    RevisionOptions,
    import_configtree,
    merge_configtree,
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
def sdk(platform: ConfigtreeTransport) -> Client:
    client = Client(
        Configuration(
            organization_guid="org-id",
            project_guid="project-id",
            v2_api_host="https://example.test",
        )
    )
    client.c.close()
    client.c = httpx.Client(transport=httpx.MockTransport(platform))
    return client


def test_editable_revision_one_batch(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    with Revision(sdk, "target", options=RevisionOptions(commit=True)) as revision:
        pending = revision.keys
        revision.store("keep", 2, metadata={})
        revision.store("remove", 3)
        pending["keep"].metadata = {"unit": "m"}
        del pending["remove"]
        assert pending is revision.keys
    assert [stage for stage, _, _ in platform.calls] == ["create", "store", "commit"]
    stored = platform.revisions[("proj", "target", revision.revision_id)]["keys"]
    assert set(stored) == {"existing", "keep"}
    assert stored["keep"]["metadata"] == {"unit": "m"}
    assert revision.keys is pending
    assert platform.revisions[("proj", "target", revision.revision_id)]["message"] == (
        "Created revision through rapyuta-io-sdk-v2"
    )


def test_empty_and_aborted_revisions_skip_batch(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    with Revision(sdk, "target", options=RevisionOptions(commit=True)):
        pass
    assert [stage for stage, _, _ in platform.calls] == ["create", "commit"]
    revision = Revision(sdk, "target", options=RevisionOptions(commit=True))

    def aborted() -> None:
        with revision:
            revision.store("discard", 1)
            message = "body failed"
            raise RuntimeError(message)

    with pytest.raises(RuntimeError, match="body failed") as captured:
        aborted()
    assert captured.value.configtree_stage == "body"
    assert captured.value.configtree_revision_id == revision.revision_id
    assert [stage for stage, _, _ in platform.calls] == ["create", "commit", "create"]


def test_unsuccessful_batch_stops_commit(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    platform.batch_response = {"success": False}
    revision = Revision(sdk, "target", options=RevisionOptions(commit=True))

    def unsuccessful() -> None:
        with revision:
            revision.store("key", "value")

    with pytest.raises(ConfigTreeMutationError) as captured:
        unsuccessful()
    assert captured.value.configtree_stage == "store"
    assert captured.value.configtree_revision_id == revision.revision_id
    assert [stage for stage, _, _ in platform.calls] == ["create", "store"]


@pytest.mark.parametrize("batch_response", [{}, {"success": None}])
def test_batch_requires_affirmative_acknowledgement(
    sdk: Client, platform: ConfigtreeTransport, batch_response: dict
) -> None:
    platform.batch_response = batch_response
    revision = Revision(sdk, "target", options=RevisionOptions(commit=True))

    with pytest.raises(ConfigTreeMutationError) as captured, revision:
        revision.store("key", "value")

    assert captured.value.configtree_stage == "store"
    assert captured.value.configtree_revision_id == revision.revision_id
    assert [stage for stage, _, _ in platform.calls] == ["create", "store"]


def test_revision_instances_are_isolated_and_single_use(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    first = Revision(sdk, "target")
    second = Revision(sdk, "target")
    assert first.keys is not second.keys
    with first:
        first.store("one", 1)
        first.store("one", 2)
    with second:
        staged = True
        second.store("discard", staged)
        second.keys.clear()
    assert [stage for stage, _, _ in platform.calls] == ["create", "store", "create"]
    with pytest.raises(RuntimeError, match="single-use"):
        first.__enter__()


def test_revision_validation_prevents_batch(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    revision = Revision(sdk, "target", options=RevisionOptions(commit=True))

    def invalid_context() -> None:
        with revision:
            revision.store("x", "value")
            revision.keys["x"].checksum = "stale"

    with pytest.raises(ConfigTreeInputError) as captured:
        invalid_context()
    assert captured.value.configtree_stage == "validate"
    assert captured.value.configtree_revision_id == revision.revision_id
    assert [stage for stage, _, _ in platform.calls] == ["create"]


@pytest.mark.parametrize("commit", [False, True])
@pytest.mark.parametrize("update_head", [False, True])
def test_import_publication_options(
    sdk: Client,
    platform: ConfigtreeTransport,
    tmp_path: Path,
    *,
    commit: bool,
    update_head: bool,
) -> None:
    path = tmp_path / "robot.json"
    path.write_text('{"name":"東京","speed":{"value":2,"metadata":{}}}')
    revision_id = import_configtree(
        sdk,
        "target",
        [path],
        options=ImportOptions(commit=commit, update_head=update_head),
    )
    stages = [stage for stage, _, _ in platform.calls]
    assert stages == ["get", "create", "store"] + (["commit"] if commit else []) + (
        ["head"] if update_head else []
    )
    created = platform.revisions[("proj", "target", revision_id)]
    assert created["committed"] is commit
    assert base64.b64decode(created["keys"]["robot/name"]["data"]).decode() == "東京"
    assert created["keys"]["robot/speed"]["metadata"] == {}
    assert platform.trees[("proj", "target")]["head"]["metadata"]["guid"] == (
        revision_id if update_head else "rev-target"
    )


def test_merge_cross_scope_and_pinned_parent(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    revision_id = merge_configtree(sdk, "target", "org/source")
    stages = [stage for stage, _, _ in platform.calls]
    assert stages == ["get", "get", "create", "store", "commit", "head"]
    assert platform.calls[1][1] == "org"
    created = platform.revisions[("proj", "target", revision_id)]
    assert created["parent"] == "rev-target"
    assert set(created["keys"]) == {"existing", "added"}
    assert platform.trees[("org", "source")]["head"]["metadata"]["guid"] == "rev-source"


def test_merge_conflict_before_create(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    platform.revisions[("org", "source", "rev-source")]["keys"]["existing"] = (
        encode_value("different").model_dump(by_alias=True, exclude_unset=True)
    )
    with pytest.raises(ConfigTreeMergeConflictError) as captured:
        merge_configtree(sdk, "target", "org/source")
    assert captured.value.conflicting_keys == ["existing"]
    assert [stage for stage, _, _ in platform.calls] == ["get", "get"]


def test_milestone_later_page_ambiguity(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    platform.page_size = 1
    source = platform.revisions[("org", "source", "rev-source")]
    source["metadata"]["labels"] = {"rapyuta.io/milestone": "release"}
    platform.revisions[("org", "source", "rev-other")] = {
        "metadata": {
            "guid": "rev-other",
            "labels": {"rapyuta.io/milestone": "release"},
        },
        "committed": True,
        "keys": {},
    }
    with pytest.raises(ConfigTreeReferenceError):
        merge_configtree(sdk, "target", "org/source/release")
    assert [stage for stage, _, _ in platform.calls] == ["get", "list", "list"]


def test_milestone_zero_ends_pagination(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    platform.page_size = 1
    platform.revisions[("org", "source", "rev-source")]["metadata"]["labels"] = {
        "rapyuta.io/milestone": "release"
    }
    platform.revisions[("org", "source", "rev-unrelated")] = {
        "metadata": {"guid": "rev-unrelated"},
        "committed": True,
        "keys": {},
    }
    revision_id = merge_configtree(sdk, "target", "org/source/release")
    assert "added" in platform.revisions[("proj", "target", revision_id)]["keys"]
    assert [stage for stage, _, _ in platform.calls] == [
        "get",
        "list",
        "list",
        "get",
        "create",
        "store",
        "commit",
        "head",
    ]


def test_source_stale_length_prevents_create(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    payload = platform.revisions[("org", "source", "rev-source")]["keys"]["added"]
    payload["contentLength"] = 1
    with pytest.raises(ConfigTreeInputError) as captured:
        merge_configtree(sdk, "target", "org/source")
    assert captured.value.key == "added"
    assert [stage for stage, _, _ in platform.calls] == ["get", "get"]


def test_explicit_historical_revision(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    platform.revisions[("org", "source", "rev-old")] = {
        "metadata": {"guid": "rev-old"},
        "committed": True,
        "keys": {
            "historical": encode_value("old").model_dump(
                by_alias=True, exclude_unset=True
            )
        },
    }
    revision_id = merge_configtree(sdk, "target", "org/source/rev-old")
    assert "historical" in platform.revisions[("proj", "target", revision_id)]["keys"]
    assert "added" not in platform.revisions[("proj", "target", revision_id)]["keys"]


def test_milestone_mismatched_label_and_bad_token(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    with pytest.raises(ConfigTreeReferenceError):
        merge_configtree(sdk, "target", "org/source/release")
    assert [stage for stage, _, _ in platform.calls] == ["get", "list"]
    platform.calls.clear()
    platform.bad_continuation = True
    with pytest.raises(
        ConfigTreeReferenceError, match="Invalid milestone continuation"
    ):
        merge_configtree(sdk, "target", "org/source/release")
    assert [stage for stage, _, _ in platform.calls] == ["get", "list", "list"]


def test_merge_reverse_scope_and_same_tree(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    reverse = merge_configtree(
        sdk, "source", "proj/target", options=MergeOptions(with_project=False)
    )
    assert platform.trees[("org", "source")]["head"]["metadata"]["guid"] == reverse
    assert {scope for _, scope, _ in platform.calls[:2]} == {"org", "proj"}
    platform.calls.clear()
    same = merge_configtree(sdk, "target", "proj/target")
    assert platform.trees[("proj", "target")]["head"]["metadata"]["guid"] == same
    assert set(platform.revisions[("proj", "target", same)]["keys"]) == {"existing"}


def test_merge_empty_union_creates_revision(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    platform.add_tree("proj", "empty", head="rev-empty")
    platform.add_tree("org", "blank", head="rev-blank")
    revision_id = merge_configtree(sdk, "empty", "org/blank")
    assert platform.revisions[("proj", "empty", revision_id)]["keys"] == {}
    assert [stage for stage, _, _ in platform.calls] == [
        "get",
        "get",
        "create",
        "commit",
        "head",
    ]


@pytest.mark.parametrize("missing_scope", ["proj", "org"])
def test_merge_rejects_omitted_key_map_before_create(
    sdk: Client, platform: ConfigtreeTransport, missing_scope: str
) -> None:
    missing_name = "target" if missing_scope == "proj" else "source"
    platform.omit_key_maps.add((missing_scope, missing_name))

    with pytest.raises(
        ConfigTreeReferenceError, match="Selected configuration key map is missing"
    ) as captured:
        merge_configtree(sdk, "target", "org/source")

    assert captured.value.configtree_stage == "resolve"
    assert [stage for stage, _, _ in platform.calls] == [
        "get",
        *(["get"] if missing_scope == "org" else []),
    ]
    assert platform.trees[("proj", "target")]["head"]["metadata"]["guid"] == (
        "rev-target"
    )


def test_merge_unacknowledged_batch_does_not_commit_or_select_head(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    platform.batch_response = {}

    with pytest.raises(ConfigTreeMutationError) as captured:
        merge_configtree(sdk, "target", "org/source")

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


def test_import_rejects_unusable_parent_and_empty_root(
    sdk: Client, platform: ConfigtreeTransport, tmp_path: Path
) -> None:
    path = tmp_path / "robot.json"
    path.write_text("{}")
    with pytest.raises(ConfigTreeInputError):
        import_configtree(sdk, "target", [path])
    assert platform.calls == []
    path.write_text('{"key":1}')
    platform.revisions[("proj", "target", "rev-target")]["committed"] = False
    with pytest.raises(ConfigTreeReferenceError):
        import_configtree(sdk, "target", [path])
    assert [stage for stage, _, _ in platform.calls] == ["get"]


def test_import_surrogate_path_fails_before_revision_creation(
    sdk: Client, platform: ConfigtreeTransport, tmp_path: Path
) -> None:
    path = tmp_path / "robot.json"
    path.write_text('{"\\ud800":1,"\\ud801":2}')

    with pytest.raises(ConfigTreeInputError) as captured:
        import_configtree(sdk, "target", [path])

    assert captured.value.file_path == str(path)
    assert platform.calls == []


def test_import_yaml_merge_override_reaches_revision(
    sdk: Client, platform: ConfigtreeTransport, tmp_path: Path
) -> None:
    path = tmp_path / "robot.yaml"
    path.write_text(
        "defaults: &defaults\n  speed: 1\n  unit: m\n"
        "settings:\n  <<: *defaults\n  speed: 2\n"
    )

    revision_id = import_configtree(sdk, "target", [path])

    stored = platform.revisions[("proj", "target", revision_id)]["keys"]
    assert stored["robot/settings/speed"]["data"] == encode_value(2).data
    assert stored["robot/settings/unit"]["data"] == encode_value("m").data
    assert [stage for stage, _, _ in platform.calls] == ["get", "create", "store"]


def test_import_scope_remains_pinned_after_configuration_change(
    sdk: Client, platform: ConfigtreeTransport, tmp_path: Path
) -> None:
    path = tmp_path / "robot.json"
    path.write_text('{"key":1}')
    original_get = sdk.get_configtree

    def change_configuration(*args: object, **kwargs: object) -> object:
        result = original_get(*args, **kwargs)
        sdk.config.organization_guid = "changed-org"
        sdk.config.project_guid = "changed-project"
        return result

    sdk.get_configtree = change_configuration
    import_configtree(sdk, "target", [path], options=ImportOptions(commit=True))
    assert [headers["organizationguid"] for headers in platform.headers] == [
        "org-id",
        "org-id",
        "org-id",
        "org-id",
    ]
    assert [headers["project"] for headers in platform.headers] == [
        "project-id",
        "project-id",
        "project-id",
        "project-id",
    ]


def test_missing_scope_is_rejected_before_requests(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    sdk.config.project_guid = " "
    with pytest.raises(ConfigTreeReferenceError) as captured:
        Revision(sdk, "target")
    assert captured.value.configtree_stage == "prepare"
    assert platform.calls == []


def test_store_reports_invalid_logical_key(
    sdk: Client, platform: ConfigtreeTransport
) -> None:
    revision = Revision(sdk, "target")

    def invalid_store() -> None:
        with revision:
            revision.store("bad", float("nan"))

    with pytest.raises(ConfigTreeInputError) as captured:
        invalid_store()
    assert captured.value.key == "bad"
    assert [stage for stage, _, _ in platform.calls] == ["create"]


def test_transport_failure_keeps_original_error_and_revision_id(
    sdk: Client, platform: ConfigtreeTransport, tmp_path: Path
) -> None:
    path = tmp_path / "robot.json"
    path.write_text('{"key":1}')

    def handler(request: httpx.Request) -> httpx.Response:
        parts = [part for part in request.url.path.split("/") if part]
        if platform.stage_for_request(request.method, parts) == "store":
            message = "connection lost"
            raise httpx.ConnectError(message)
        return platform(request)

    sdk.c.close()
    sdk.c = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.ConnectError) as captured:
        import_configtree(sdk, "target", [path])
    assert captured.value.configtree_stage == "store"
    assert captured.value.configtree_revision_id == "rev-new-1"
    assert [stage for stage, _, _ in platform.calls] == ["get", "create"]


@pytest.mark.parametrize("stage", ["create", "store", "commit", "head"])
def test_import_failure_stage_and_recovery(
    sdk: Client,
    platform: ConfigtreeTransport,
    tmp_path: Path,
    *,
    stage: str,
) -> None:
    platform.fail_stage = stage
    path = tmp_path / "robot.json"
    path.write_text('{"key":1}')
    with pytest.raises(ServiceUnavailableError) as captured:
        import_configtree(
            sdk, "target", [path], options=ImportOptions(commit=True, update_head=True)
        )
    assert captured.value.configtree_stage == stage
    if stage != "create":
        assert captured.value.configtree_revision_id == "rev-new-1"
    assert [s for s, _, _ in platform.calls][-1] == stage
