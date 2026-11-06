# Copyright 2026 Rapyuta Robotics
"""Explicit environment configuration for executable Device examples."""

import os

from rapyuta_io_sdk_v2 import Configuration


def configuration() -> Configuration:
    """Read example credentials, source context and optional service origin."""
    return Configuration(
        auth_token=os.environ.get("RAPYUTA_AUTH_TOKEN"),
        project_guid=os.environ.get("RAPYUTA_PROJECT_GUID"),
        organization_guid=os.environ.get("RAPYUTA_ORGANIZATION_GUID"),
        environment=os.environ.get("RAPYUTA_ENVIRONMENT", "ga"),
        core_api_host=os.environ.get("RAPYUTA_CORE_API_HOST"),
    )
