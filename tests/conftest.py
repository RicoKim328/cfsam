# SPDX-License-Identifier: Apache-2.0
"""Shared test harness: cFS fixture trees and golden-file snapshots.

Fixture trees live in tests/fixtures/cfs_<name>/ and mirror the layout of the
cFS bundle (paths relative to the bundle root). Tests never read the real
bundle in ../, so they stay reproducible.

Golden files live in tests/golden/. Compare with the ``golden`` fixture:

    def test_import(golden):
        golden.check("cfs_sample/mission.yaml", produced_text)

Run ``pytest --update-golden`` to (re)write snapshots, then review the diff.
"""
from __future__ import annotations

import difflib
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
GOLDEN_DIR = TESTS_DIR / "golden"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        help="rewrite golden files in tests/golden/ instead of comparing",
    )


@pytest.fixture
def cfs_fixture():
    """Return the root of a fixture tree, e.g. ``cfs_fixture("sample")``."""

    def _get(name: str) -> Path:
        root = FIXTURES_DIR / f"cfs_{name}"
        if not root.is_dir():
            raise FileNotFoundError(f"no fixture tree {root}")
        return root

    return _get


class Golden:
    def __init__(self, update: bool) -> None:
        self.update = update

    def check(self, relpath: str, actual: str) -> None:
        path = GOLDEN_DIR / relpath
        if self.update:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(actual, encoding="utf-8")
            return
        if not path.exists():
            pytest.fail(f"missing golden file {path}; run pytest --update-golden")
        expected = path.read_text(encoding="utf-8")
        if actual != expected:
            diff = difflib.unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile=f"golden/{relpath}",
                tofile="actual",
            )
            pytest.fail("golden mismatch:\n" + "".join(diff))


@pytest.fixture
def golden(request: pytest.FixtureRequest) -> Golden:
    return Golden(request.config.getoption("--update-golden"))
