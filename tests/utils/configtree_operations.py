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

"""Stateful MockTransport for scoped configuration tree workflow tests."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field

import httpx


@dataclass
class ConfigtreeTransport:
    """Record requests and simulate revision creation, storage, and publication."""

    trees: dict[tuple[str, str], dict] = field(default_factory=dict)
    revisions: dict[tuple[str, str, str], dict] = field(default_factory=dict)
    calls: list[tuple[str, str, str]] = field(default_factory=list)
    headers: list[dict[str, str]] = field(default_factory=list)
    fail_stage: str | None = None
    batch_response: dict = field(default_factory=lambda: {"success": True})
    omit_key_maps: set[tuple[str, str]] = field(default_factory=set)
    page_size: int | None = None
    bad_continuation: bool = False
    next_id: int = 1

    def add_tree(
        self,
        scope: str,
        name: str,
        *,
        head: str,
        keys: dict | None = None,
    ) -> None:
        """Install one committed selected revision and its key map."""
        self.trees[(scope, name)] = {
            "metadata": {"name": name},
            "head": {"metadata": {"guid": head}, "committed": True},
        }
        self.revisions[(scope, name, head)] = {
            "metadata": {"guid": head},
            "committed": True,
            "keys": copy.deepcopy(keys or {}),
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        """Route a typed SDK request to the in-memory platform state."""
        scope = "proj" if "project" in request.headers else "org"
        parts = [part for part in request.url.path.split("/") if part]
        name = parts[2]
        stage = self.stage_for_request(request.method, parts)
        self.calls.append((stage, scope, name))
        self.headers.append(dict(request.headers))
        if stage == self.fail_stage:
            return httpx.Response(503, json={"error": "injected failure"})
        payload = json.loads(request.content) if request.content else None
        handler = getattr(self, f"_handle_{stage}")
        return handler(request, scope=scope, name=name, payload=payload)

    def _handle_get(
        self,
        request: httpx.Request,
        *,
        scope: str,
        name: str,
        payload: dict | None,  # noqa: ARG002
    ) -> httpx.Response:
        tree = copy.deepcopy(self.trees[(scope, name)])
        revision_id = (
            request.url.params.get("revision") or tree["head"]["metadata"]["guid"]
        )
        revision = self.revisions[(scope, name, revision_id)]
        tree["head"] = {key: value for key, value in revision.items() if key != "keys"}
        if (
            request.url.params.get("includeData") == "true"
            and (scope, name) not in self.omit_key_maps
        ):
            tree["keys"] = copy.deepcopy(revision["keys"])
        return httpx.Response(200, json=tree)

    def _handle_list(
        self,
        _request: httpx.Request,
        *,
        scope: str,
        name: str,
        payload: dict | None,  # noqa: ARG002
    ) -> httpx.Response:
        items = [
            v for (s, n, _), v in self.revisions.items() if (s, n) == (scope, name)
        ]
        offset = int(_request.url.params.get("continue", "0"))
        end = offset + (self.page_size or len(items))
        continuation = end if end < len(items) else 0
        if self.bad_continuation:
            continuation = offset or 1
        return httpx.Response(
            200,
            json={"items": items[offset:end], "metadata": {"continue": continuation}},
        )

    def _handle_create(
        self,
        _request: httpx.Request,
        *,
        scope: str,
        name: str,
        payload: dict | None,
    ) -> httpx.Response:
        revision_id = f"rev-new-{self.next_id}"
        self.next_id += 1
        parent = (
            payload.get("parent")
            if payload
            else self.trees[(scope, name)]["head"]["metadata"]["guid"]
        )
        keys = copy.deepcopy(self.revisions[(scope, name, parent)]["keys"])
        self.revisions[(scope, name, revision_id)] = {
            "metadata": {"guid": revision_id},
            "parent": parent,
            "committed": False,
            "keys": keys,
        }
        return httpx.Response(201, json={"metadata": {"guid": revision_id}})

    def _handle_store(
        self, request: httpx.Request, *, scope: str, name: str, payload: dict | None
    ) -> httpx.Response:
        revision_id = request.url.path.split("/")[5]
        self.revisions[(scope, name, revision_id)]["keys"].update(payload)
        return httpx.Response(200, json=self.batch_response)

    def _handle_commit(
        self, request: httpx.Request, *, scope: str, name: str, payload: dict | None
    ) -> httpx.Response:
        revision_id = request.url.path.split("/")[5]
        revision = self.revisions[(scope, name, revision_id)]
        revision["committed"] = True
        revision["message"] = payload["message"]
        return httpx.Response(
            200, json={"metadata": {"guid": revision_id}, "committed": True}
        )

    def _handle_head(
        self,
        _request: httpx.Request,
        *,
        scope: str,
        name: str,
        payload: dict | None,
    ) -> httpx.Response:
        self.trees[(scope, name)]["head"] = payload["head"]
        return httpx.Response(200, json=self.trees[(scope, name)])

    @staticmethod
    def stage_for_request(method: str, parts: list[str]) -> str:
        """Classify a low-level request by its platform mutation stage."""
        tree_depth = 3
        revision_collection_depth = 4
        if len(parts) == tree_depth:
            return "head" if method == "PUT" else "get"
        if len(parts) == revision_collection_depth:
            return "create" if method == "POST" else "list"
        return "store" if method == "PUT" else "commit"
