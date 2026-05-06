"""Integration test for the Java runner-helper round-trip.

Verifies that:
  - On the CLEAN sample, the hand-written LLM01 test PASSES (exit 0).
  - On the BUGGY variant (after `llm01_remove_sanitization` injection),
    the same test FAILS (exit 1).

Marked `integration` because it requires:
  - JDK 17+ on PATH (`javac`, `java`)
  - `engine/eval/runner-helper/setup.py` to have been run (lib/*.jar
    populated, TestRunner.class compiled)

Skips automatically when those preconditions aren't met, so it's safe to
include in the default pytest collection. CI can set the integration
mark to skip-by-default without losing this signal locally.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ENGINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_ROOT))

from eval.injections import Llm01RemoveSanitization  # noqa: E402

RUNNER_DIR = ENGINE_ROOT / "eval" / "runner-helper"
SAMPLE_PATH = ENGINE_ROOT / "eval" / "samples" / "spring_ai" / "RestaurantPromptAssembler.java"
TEST_CLASS_PATH = RUNNER_DIR / "smoke" / "RestaurantPromptAssemblerAgentGenTest.java"
TEST_CLASS_FQN = "com.example.spring.RestaurantPromptAssemblerAgentGenTest"


def _runner_helper_ready() -> bool:
    if shutil.which("java") is None:
        return False
    if not (RUNNER_DIR / "TestRunner.class").exists():
        return False
    return any(RUNNER_DIR.glob("lib/*.jar"))


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _runner_helper_ready(),
        reason=(
            "runner-helper not set up; run "
            "`python engine/eval/runner-helper/setup.py` once"
        ),
    ),
]


def _classpath() -> str:
    # Java's classpath separator is OS-specific.
    sep = ";" if sys.platform.startswith("win") else ":"
    return f"lib/*{sep}."


def _run_helper(target_path: Path, test_path: Path, fqn: str) -> tuple[int, str]:
    """Invoke TestRunner; return (exit_code, combined stdout/stderr)."""
    cmd = [
        "java",
        "-cp", _classpath(),
        f"-Dagenttest.runner.dir={RUNNER_DIR}",
        "TestRunner",
        str(target_path),
        str(test_path),
        fqn,
    ]
    proc = subprocess.run(
        cmd,
        cwd=RUNNER_DIR,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    return proc.returncode, proc.stdout + proc.stderr


def test_helper_returns_pass_on_clean_sample() -> None:
    """The hand-written LLM01 test should PASS on the clean assembler."""
    rc, out = _run_helper(SAMPLE_PATH, TEST_CLASS_PATH, TEST_CLASS_FQN)
    assert rc == 0, f"expected PASS (exit 0), got exit {rc}\n{out}"
    assert out.startswith("PASS"), f"expected output to start with 'PASS', got:\n{out}"


def test_helper_returns_fail_on_buggy_sample(tmp_path: Path) -> None:
    """After llm01_remove_sanitization, the same test should FAIL."""
    clean = SAMPLE_PATH.read_text(encoding="utf-8")
    buggy = Llm01RemoveSanitization().apply(clean)
    buggy_path = tmp_path / "RestaurantPromptAssembler.java"
    buggy_path.write_text(buggy, encoding="utf-8")

    rc, out = _run_helper(buggy_path, TEST_CLASS_PATH, TEST_CLASS_FQN)
    assert rc == 1, f"expected FAIL (exit 1), got exit {rc}\n{out}"
    assert out.startswith("FAIL"), f"expected output to start with 'FAIL', got:\n{out}"
    # AssertJ's failure message should reference the breakout payload, so
    # we know the test caught the right bug, not some other accident.
    assert "IGNORE ABOVE INSTRUCTIONS" in out, (
        f"expected breakout payload in failure trace, got:\n{out}"
    )
