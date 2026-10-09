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


from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from rapyuta_io_sdk_v2.models import BulkRoleBindingUpdate

if TYPE_CHECKING:
    from pytest_mock import MockFixture

    from rapyuta_io_sdk_v2 import Client


@pytest.mark.parametrize(
    ("filter_name", "query_name"),
    [
        ("label_selector", "labelSelector"),
        ("role_names", "roleNames"),
        ("subject_guids", "subjectGUIDS"),
        ("subject_names", "subjectNames"),
        ("subject_kinds", "subjectKinds"),
        ("domain_guids", "domainGUIDS"),
        ("domain_names", "domainNames"),
        ("domain_kinds", "domainKinds"),
        ("guids", "guids"),
    ],
)
def test_list_role_bindings_uses_api_filter_names(
    *,
    client: Client,
    mocker: MockFixture,
    filter_name: str,
    query_name: str,
) -> None:
    request = mocker.patch("httpx.Client.get")
    request.return_value = httpx.Response(httpx.codes.OK, json={"items": []})
    client.list_role_bindings(**{filter_name: ["selected"]})
    assert request.call_args.kwargs["params"][query_name] == ["selected"]


def test_list_role_bindings_omits_empty_filters(
    *,
    client: Client,
    mocker: MockFixture,
) -> None:
    request = mocker.patch("httpx.Client.get")
    request.return_value = httpx.Response(httpx.codes.OK, json={"items": []})
    client.list_role_bindings(role_names=[], label_selector=[])
    assert set(request.call_args.kwargs["params"]) == {"continue", "limit"}


def test_update_role_binding_returns_bulk_response(
    *, client: Client, mocker: MockFixture
) -> None:
    request = mocker.patch("httpx.Client.put")
    request.return_value = httpx.Response(
        httpx.codes.OK, json={"newBindings": [], "oldBindings": []}
    )
    response = client.update_role_binding(
        BulkRoleBindingUpdate.model_validate({"newBindings": [], "oldBindings": []})
    )
    assert isinstance(response, BulkRoleBindingUpdate)
    assert response.new_bindings == []
    assert response.old_bindings == []


def test_update_role_binding_propagates_unexpected_model_error(
    *,
    client: Client,
    mocker: MockFixture,
) -> None:
    request = mocker.patch("httpx.Client.put")
    request.return_value = httpx.Response(
        httpx.codes.OK, json={"newBindings": [], "oldBindings": []}
    )
    mocker.patch(
        "rapyuta_io_sdk_v2.client.BulkRoleBindingUpdate",
        side_effect=RuntimeError("unexpected model error"),
    )
    with pytest.raises(RuntimeError, match=r"^unexpected model error$"):
        client.update_role_binding(
            BulkRoleBindingUpdate.model_validate({"newBindings": [], "oldBindings": []})
        )
