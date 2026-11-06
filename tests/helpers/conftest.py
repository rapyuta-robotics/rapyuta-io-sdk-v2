# Copyright 2026 Rapyuta Robotics

"""Shared temporary sources and isolated upload service fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.data.parameter_data import ParameterService

if TYPE_CHECKING:
    from pathlib import Path


def mixed_source(root: Path) -> Path:
    """Create two trees, one hundred mixed files and five directory levels."""
    for tree in ("alpha", "beta"):
        parent = root / tree / "one" / "two" / "three" / "four" / "five"
        parent.mkdir(parents=True)
        (root / tree / "empty").mkdir()
        for index in range(50):
            extension = "yaml" if index % 2 else "bin"
            content = (
                b"key: caf\xc3\xa9\r\n" if extension == "yaml" else bytes([index]) * 25
            )
            (parent / f"file{index}.{extension}").write_bytes(content)
    (root / "loose.txt").write_bytes(b"skip")
    return root


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """Return the acceptance fixture source."""
    return mixed_source(tmp_path / "source")


@pytest.fixture
def service() -> ParameterService:
    """Return an empty isolated Parameter/blob service."""
    return ParameterService()


@pytest.fixture
def failure_source(tmp_path: Path) -> Path:
    """Complete one inline file before a staged blob fails; retain later work."""
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.yaml").write_text("key: confirmed\n")
    (tree / "b.bin").write_bytes(b"z" * 4194305)
    (tree / "c.bin").write_bytes(b"later")
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha/done.yaml").write_text("done: true\n")
    return tmp_path
