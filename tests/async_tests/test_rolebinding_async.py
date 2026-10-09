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

    from rapyuta_io_sdk_v2 import AsyncClient


@pytest.mark.asyncio
async def test_list_role_bindings_uses_api_filter_names_and_omits_empty_filters(
    *,
    async_client: AsyncClient,
    mocker: MockFixture,
) -> None:
    request = mocker.patch("httpx.AsyncClient.get")
    request.return_value = httpx.Response(httpx.codes.OK, json={"items": []})
    await async_client.list_role_bindings(subject_guids=["subject"], domain_names=[])
    assert request.call_args.kwargs["params"]["subjectGUIDS"] == ["subject"]
    assert "domainNames" not in request.call_args.kwargs["params"]


@pytest.mark.asyncio
async def test_update_role_binding_returns_bulk_response(
    *,
    async_client: AsyncClient,
    mocker: MockFixture,
) -> None:
    request = mocker.patch("httpx.AsyncClient.put")
    request.return_value = httpx.Response(
        httpx.codes.OK, json={"newBindings": [], "oldBindings": []}
    )
    response = await async_client.update_role_binding(
        BulkRoleBindingUpdate.model_validate({"newBindings": [], "oldBindings": []})
    )
    assert isinstance(response, BulkRoleBindingUpdate)
    assert response.new_bindings == []
    assert response.old_bindings == []


@pytest.mark.asyncio
async def test_update_role_binding_propagates_unexpected_model_error(
    *,
    async_client: AsyncClient,
    mocker: MockFixture,
) -> None:
    request = mocker.patch("httpx.AsyncClient.put")
    request.return_value = httpx.Response(
        httpx.codes.OK, json={"newBindings": [], "oldBindings": []}
    )
    mocker.patch(
        "rapyuta_io_sdk_v2.async_client.BulkRoleBindingUpdate",
        side_effect=RuntimeError("unexpected model error"),
    )
    with pytest.raises(RuntimeError, match=r"^unexpected model error$"):
        await async_client.update_role_binding(
            BulkRoleBindingUpdate.model_validate({"newBindings": [], "oldBindings": []})
        )
