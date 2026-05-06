"""Run-on-clean gate for generator output.

Wraps a generated test method body into a class skeleton, writes both
the test source and the (already-on-disk) target source to a temp
directory, and shells out to the Java runner-helper at
`engine/eval/runner-helper/TestRunner`. Returns a structured
`RunResult` mirroring the helper's `PASS / FAIL / COMPILE_FAIL /
ERROR` token contract.

Sync subprocess for now: the validator is on the request path BUT the
call is short and bounded (60s timeout). TODO(S3): convert to
`asyncio.create_subprocess_exec` once SSE is wired so the validator
doesn't block the event loop while the JVM runs.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


_ENGINE_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # .../engine/
_RUNNER_DIR = _ENGINE_ROOT / "eval" / "runner-helper"

RunOutcome = Literal["PASS", "FAIL", "COMPILE_FAIL", "ERROR"]


@dataclass(frozen=True)
class RunResult:
    outcome: RunOutcome
    details: str
    exit_code: int


def runner_helper_dir() -> Path:
    """Return the absolute path to the runner-helper directory."""
    return _RUNNER_DIR


def runner_helper_ready() -> bool:
    """True iff the helper is set up and `java` is on PATH.

    Used by the integration tests to skip cleanly when the helper
    isn't built. The CLI / pipeline prefer to fail loudly when the
    helper is missing on a real run — silent fallback would let a
    grader run a degraded pipeline and not know it (per
    `docs/plan/sprint-2.md` § "Locked decision 3").
    """
    if shutil.which("java") is None:
        return False
    if not (_RUNNER_DIR / "TestRunner.class").exists():
        return False
    return any(_RUNNER_DIR.glob("lib/*.jar"))


def wrap_test_method(
    test_method_source: str,
    *,
    target_class_name: str,
    target_package: str,
) -> tuple[str, str]:
    """Wrap a single `@Test` method body into a JUnit 5 + AssertJ class.

    Returns `(java_source, fully_qualified_class_name)`.

    The class is named `<TargetClass>AgentGenTest`. The package
    matches the target so the test can `new <TargetClass>()` without
    an extra import (Java imports the same-package class implicitly).
    """
    test_class_name = f"{target_class_name}AgentGenTest"
    fqn = f"{target_package}.{test_class_name}" if target_package else test_class_name

    package_line = f"package {target_package};\n\n" if target_package else ""

    java_source = (
        package_line
        + "import org.junit.jupiter.api.Test;\n"
        + "import static org.assertj.core.api.Assertions.assertThat;\n\n"
        + f"class {test_class_name} {{\n"
        + "\n"
        + _indent(test_method_source.rstrip(), "    ")
        + "\n"
        + "}\n"
    )
    return java_source, fqn


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else line for line in text.split("\n"))


def _classpath() -> str:
    """Java classpath for invoking TestRunner from inside `_RUNNER_DIR`.

    `os.pathsep` is `:` on POSIX and `;` on Windows.
    """
    return f"lib/*{os.pathsep}."


def run_on_clean(
    target_class_path: Path,
    test_class_source: str,
    test_class_fqn: str,
    *,
    timeout: int = 60,
) -> RunResult:
    """Compile + run the generated test against the *clean* target class.

    `target_class_path` is the path to the user's input .java file
    (already on disk). `test_class_source` is the full Java source
    of the wrapped test class. `test_class_fqn` is its fully-
    qualified name (matches the package + class).
    """
    if shutil.which("java") is None:
        return RunResult(
            outcome="ERROR",
            details="`java` not on PATH — install JDK 17+ first",
            exit_code=-1,
        )
    if not (_RUNNER_DIR / "TestRunner.class").exists():
        return RunResult(
            outcome="ERROR",
            details=(
                f"runner-helper not set up at {_RUNNER_DIR}; "
                "run `python engine/eval/runner-helper/setup.py` once"
            ),
            exit_code=-1,
        )

    with tempfile.TemporaryDirectory(prefix="agenttest-validator-") as tmp:
        test_path = Path(tmp) / f"{test_class_fqn.split('.')[-1]}.java"
        test_path.write_text(test_class_source, encoding="utf-8")

        cmd = [
            "java",
            "-cp", _classpath(),
            f"-Dagenttest.runner.dir={_RUNNER_DIR}",
            "TestRunner",
            str(target_class_path.resolve()),
            str(test_path.resolve()),
            test_class_fqn,
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=_RUNNER_DIR,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return RunResult(
                outcome="ERROR",
                details=f"runner-helper timed out after {timeout}s: {exc}",
                exit_code=-1,
            )

    combined = (proc.stdout or "") + (proc.stderr or "")
    first_line = combined.splitlines()[0].strip() if combined.strip() else ""
    details = combined[len(first_line):].lstrip("\n") if first_line else combined

    outcome: RunOutcome
    if first_line == "PASS":
        outcome = "PASS"
    elif first_line == "FAIL":
        outcome = "FAIL"
    elif first_line == "COMPILE_FAIL":
        outcome = "COMPILE_FAIL"
    else:
        outcome = "ERROR"
        if not first_line:
            details = (
                f"runner-helper produced no recognizable token "
                f"(exit={proc.returncode}); raw output:\n{combined}"
            )

    return RunResult(outcome=outcome, details=details, exit_code=proc.returncode)


# Re-export for tests that want to know the helper directory.
__all__ = [
    "RunResult",
    "RunOutcome",
    "run_on_clean",
    "wrap_test_method",
    "runner_helper_dir",
    "runner_helper_ready",
]
