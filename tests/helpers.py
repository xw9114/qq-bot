from __future__ import annotations

import re
import shutil
from pathlib import Path
from unittest import TestCase
from uuid import uuid4


TEST_ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / ".test_artifacts"
_SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")


def isolated_test_path(test_case: TestCase, filename: str) -> Path:
    test_dir = TEST_ARTIFACTS_DIR / _safe_name(test_case.id()) / uuid4().hex
    test_dir.mkdir(parents=True, exist_ok=False)
    test_case.addCleanup(_remove_test_dir, test_dir)
    return test_dir / filename


def _safe_name(value: str) -> str:
    return _SAFE_NAME_PATTERN.sub("_", value).strip("_") or "test"


def _remove_test_dir(test_dir: Path) -> None:
    root = TEST_ARTIFACTS_DIR.resolve()
    target = test_dir.resolve()
    target.relative_to(root)
    shutil.rmtree(target, ignore_errors=True)
