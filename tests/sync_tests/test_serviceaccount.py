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


from typing import Any

import pytest

from rapyuta_io_sdk_v2.models import ServiceAccount


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"metadata": {"name": "service"}}, []),
        (
            {
                "metadata": {"name": "service"},
                "spec": {
                    "roles": [
                        {
                            "domain": {"kind": "Project", "guid": "project-guid"},
                            "roleNames": ["reader"],
                        },
                    ]
                },
            },
            ["role:reader"],
        ),
    ],
)
def test_service_account_list_dependencies_handles_roles_and_empty_results(
    *, payload: dict[str, Any], expected: list[str] | None
) -> None:
    resource = ServiceAccount.model_validate(payload)
    assert resource.list_dependencies() == expected
