# Copyright 2026 Rapyuta Robotics
"""Shared checks against immutable controller goldens."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx

from rapyuta_io_sdk_v2 import models
from tests.data.device_data import BASE

if TYPE_CHECKING:
    from tests.data.device_data import DeviceCase


def arguments(case: DeviceCase) -> tuple[list[object], dict[str, object]]:
    args: list[object] = list(case.args)
    keywords: dict[str, object] = {}
    if case.model:
        body = getattr(models, case.model).model_validate_json(case.body)
        if case.name == "get_device_command_result":
            keywords["query"] = body
        else:
            args.append(body)
    return args, keywords


def verify_request(request: httpx.Request, case: DeviceCase) -> httpx.Response:
    assert request.method == case.verb
    assert request.url.path == BASE + case.path
    assert tuple(request.url.params.multi_items()) == case.query
    if case.body and case.name != "get_device_command_result":
        expected = json.loads(case.body)
        if case.name == "update_device":
            expected["device_id"] = case.args[0]
        if case.name == "execute_device_command":
            expected.update(timeout=300, bg=False, run_async=False, env={})
        assert json.loads(request.content) == expected
    return httpx.Response(200, content=case.response)
