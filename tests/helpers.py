from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase
from uuid import uuid4


TEST_ARTIFACTS_ENV_VAR = "QQ_CLAUDE_BOT_TEST_ARTIFACTS_DIR"
TEST_ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / ".test_artifacts"
FALLBACK_TEST_ARTIFACTS_DIR = Path(tempfile.gettempdir()) / "qq-claude-bot-test-artifacts"
_SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")


def isolated_test_path(test_case: TestCase, filename: str) -> Path:
    last_error: OSError | None = None
    for root in _test_artifact_roots():
        test_dir = root / _safe_name(test_case.id()) / uuid4().hex
        try:
            test_dir.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            last_error = exc
            continue

        test_case.addCleanup(_remove_test_dir, test_dir, root)
        return test_dir / filename

    raise RuntimeError("没有可写的测试产物目录") from last_error


def _test_artifact_roots() -> tuple[Path, ...]:
    configured_dir = os.environ.get(TEST_ARTIFACTS_ENV_VAR)
    if configured_dir:
        return (Path(configured_dir).expanduser(),)
    return (TEST_ARTIFACTS_DIR, FALLBACK_TEST_ARTIFACTS_DIR)


def _safe_name(value: str) -> str:
    return _SAFE_NAME_PATTERN.sub("_", value).strip("_") or "test"


def _remove_test_dir(test_dir: Path, root: Path) -> None:
    root = root.resolve()
    target = test_dir.resolve()
    target.relative_to(root)
    shutil.rmtree(target, ignore_errors=True)
