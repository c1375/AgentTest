"""Eval runner.

Iterates over `eval/samples/**/*.meta.yaml`, runs the AgentTest pipeline
on each sample's clean Java, and for every applicable injection measures:

  - Recall@class:  did at least one generated test FAIL on the buggy
                   variant? (per docs/project_plan.md § 5)
  - Precision:     did all generated tests PASS on the clean variant?

Both measurements re-use `validator.run.run_on_clean` to invoke the Java
runner-helper — one helper, two callers (the validator-gate and us).
The function name is misleading for the buggy invocation; semantically
it's just "compile + run this test class against this target", which is
what we need.

Run from `engine/`:

    py -3.13 eval/runner.py

Writes one timestamped JSON file under `eval/results/` per run and
prints a one-line summary to stdout.

Layering note: this module sits under `eval/`, not `src/agenttest/`. The
pipeline depends on `agenttest.*` only; the eval harness depends on
both `agenttest.*` AND on local `eval/injections`. That's fine — the
arrow is one-directional (eval -> agenttest), and `eval/` is offline
analysis tooling, not request-path code.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

ENGINE_ROOT = Path(__file__).resolve().parent.parent
# `eval/` is a sibling of `src/`, not a package under `agenttest`; make
# `eval.injections` importable for both this module (when run as a
# script) and the integration tests.
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from agenttest import pipeline  # noqa: E402
from agenttest.validator.run import run_on_clean  # noqa: E402
from eval.injections import INJECTIONS_BY_NAME  # noqa: E402
from eval.results import EvalResult, SampleResult, SummaryStats  # noqa: E402

logger = logging.getLogger(__name__)


_REQUIRED_META_FIELDS = (
    "sample_id",
    "target_class",
    "target_package",
    "applicable_injections",
)


def _load_meta(meta_path: Path) -> dict:
    """Load and shallow-validate a sample's meta.yaml."""
    raw = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{meta_path} did not parse to a mapping")
    missing = [f for f in _REQUIRED_META_FIELDS if f not in raw]
    if missing:
        raise ValueError(f"{meta_path} missing required fields: {missing}")
    return raw


def _resolve_clean_java_path(meta_path: Path, target_class: str) -> Path:
    """Sibling .java file named after the target class."""
    candidate = meta_path.parent / f"{target_class}.java"
    if not candidate.exists():
        raise FileNotFoundError(
            f"expected {candidate} next to {meta_path.name}; not found"
        )
    return candidate


def _test_fqn(target_package: str, target_class: str) -> str:
    name = f"{target_class}SecurityGenTest"
    return f"{target_package}.{name}" if target_package else name


def _summarize(results: list[SampleResult]) -> SummaryStats:
    total = len(results)
    measured = [r for r in results if r.status == "measured"]
    n_measured = len(measured)
    no_tests = sum(1 for r in results if r.status == "no_tests_emitted")
    errors = sum(1 for r in results if r.status == "pipeline_error")

    if n_measured == 0:
        recall = 0.0
        precision = 0.0
    else:
        recall = sum(1 for r in measured if r.recall_caught) / n_measured
        precision = sum(1 for r in measured if r.precision_clean_pass) / n_measured

    return SummaryStats(
        total_pairs=total,
        measured_pairs=n_measured,
        recall_at_class=recall,
        precision=precision,
        no_tests_emitted=no_tests,
        pipeline_errors=errors,
    )


def _filesystem_safe_timestamp(now: datetime) -> str:
    """ISO8601-ish timestamp with `:` swapped for `-` (Windows filesystems)."""
    return now.strftime("%Y-%m-%dT%H-%M-%S")


def _error_row(
    sample_id: str,
    injection_name: str,
    error: str,
) -> SampleResult:
    return SampleResult(
        sample_id=sample_id,
        injection_name=injection_name,
        status="pipeline_error",
        tests_emitted=0,
        refused_sites=0,
        clean_outcome=None,
        buggy_outcome=None,
        recall_caught=False,
        precision_clean_pass=False,
        error=error,
    )


async def _measure_pair(
    sample_id: str,
    injection_name: str,
    clean_java_path: Path,
    test_fqn: str,
    target_class: str,
) -> SampleResult:
    """Run the pipeline + recall + precision for one (sample, injection).

    The whole body sits inside one broad try/except. **This is the only
    place a bare `except Exception:` is acceptable in the codebase**,
    because the eval runner is offline analysis tooling and one broken
    pair must not abort the whole run. The error is recorded per-pair
    via `status="pipeline_error"`.
    """
    try:
        emission = await pipeline.run(clean_java_path)

        tests_emitted = len(emission.risks_covered)
        refused = len(emission.refused_sites)

        if tests_emitted == 0:
            return SampleResult(
                sample_id=sample_id,
                injection_name=injection_name,
                status="no_tests_emitted",
                tests_emitted=0,
                refused_sites=refused,
                clean_outcome=None,
                buggy_outcome=None,
                recall_caught=False,
                precision_clean_pass=False,
                error=None,
            )

        injection_cls = INJECTIONS_BY_NAME.get(injection_name)
        if injection_cls is None:
            # Unknown injection: surface as a pipeline_error row instead
            # of silently skipping (a typo in meta.yaml is a config bug
            # that should appear in the audit trail).
            raise ValueError(f"unknown injection: {injection_name!r}")

        clean_source = clean_java_path.read_text(encoding="utf-8")
        buggy_source = injection_cls().apply(clean_source)

        # run_on_clean takes the target class as a path on disk, so the
        # buggy variant needs a real file. Java requires the filename
        # to match the public class, hence the `<target_class>.java`
        # naming.
        with tempfile.TemporaryDirectory(prefix="agenttest-eval-buggy-") as buggy_dir:
            buggy_path = Path(buggy_dir) / f"{target_class}.java"
            buggy_path.write_text(buggy_source, encoding="utf-8")

            # Precision: clean source, generated tests should all PASS.
            # Recall:    buggy source, at least one generated test should FAIL.
            # Both invocations are sync subprocess calls; off-load to a
            # thread so we don't stall the event loop. `return_exceptions=True`
            # ensures both threads always reach completion before the
            # tempdir is reaped — otherwise an exception from one
            # subprocess could exit the `with` while the other JVM
            # still holds the buggy file open (Windows would then fail
            # the rmtree).
            results = await asyncio.gather(
                asyncio.to_thread(
                    run_on_clean,
                    target_class_path=clean_java_path,
                    test_class_source=emission.java_source,
                    test_class_fqn=test_fqn,
                ),
                asyncio.to_thread(
                    run_on_clean,
                    target_class_path=buggy_path,
                    test_class_source=emission.java_source,
                    test_class_fqn=test_fqn,
                ),
                return_exceptions=True,
            )
        clean_result, buggy_result = results
        for r in (clean_result, buggy_result):
            if isinstance(r, BaseException):
                raise r

        return SampleResult(
            sample_id=sample_id,
            injection_name=injection_name,
            status="measured",
            tests_emitted=tests_emitted,
            refused_sites=refused,
            clean_outcome=clean_result.outcome,
            buggy_outcome=buggy_result.outcome,
            recall_caught=buggy_result.outcome == "FAIL",
            precision_clean_pass=clean_result.outcome == "PASS",
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[eval] error on %s / %s", sample_id, injection_name)
        return _error_row(sample_id, injection_name, f"{type(exc).__name__}: {exc}")


async def run_eval(
    samples_dir: Path = Path("eval/samples"),
    results_dir: Path = Path("eval/results"),
) -> EvalResult:
    """Run the eval harness across every (sample, applicable injection) pair.

    Paths default to relative `eval/...`, matching the README's
    instructions to invoke from `engine/`. They're resolved against the
    current working directory, so callers can pass absolute paths if
    they prefer.
    """
    samples_dir = samples_dir.resolve()
    results_dir = results_dir.resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    meta_paths = sorted(samples_dir.glob("**/*.meta.yaml"))
    logger.info("[eval] discovered %d sample(s) under %s", len(meta_paths), samples_dir)

    rows: list[SampleResult] = []
    for meta_path in meta_paths:
        meta = _load_meta(meta_path)
        sample_id = meta["sample_id"]
        target_class = meta["target_class"]
        target_package = meta["target_package"] or ""
        injections = meta["applicable_injections"] or []

        clean_java_path = _resolve_clean_java_path(meta_path, target_class)
        test_fqn = _test_fqn(target_package, target_class)

        for injection_name in injections:
            # Unknown-injection handling lives inside _measure_pair so
            # the unknown name still produces a row in the JSON audit
            # trail (instead of a silent skip).
            logger.info("[eval] running %s / %s", sample_id, injection_name)
            row = await _measure_pair(
                sample_id=sample_id,
                injection_name=injection_name,
                clean_java_path=clean_java_path,
                test_fqn=test_fqn,
                target_class=target_class,
            )
            rows.append(row)

    now = datetime.now(UTC)
    summary = _summarize(rows)
    result = EvalResult(
        timestamp_utc=now.isoformat(),
        samples=rows,
        summary=summary,
    )

    out_path = results_dir / f"run-{_filesystem_safe_timestamp(now)}.json"
    out_path.write_text(
        json.dumps(asdict(result), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    print(
        f"Eval complete: {summary.measured_pairs}/{summary.total_pairs} "
        f"measured pairs | "
        f"Recall@class={summary.recall_at_class * 100:.1f}% | "
        f"Precision={summary.precision * 100:.1f}%"
    )
    try:
        rel = out_path.relative_to(Path.cwd())
        print(f"Results: {rel}")
    except ValueError:
        print(f"Results: {out_path}")

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(run_eval())
