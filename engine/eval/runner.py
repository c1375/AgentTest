"""Eval runner.

Iterates over `eval/samples/**/*.meta.yaml`, runs either the AgentTest
pipeline OR the single-prompt baseline on each sample's clean Java,
and for every applicable injection measures:

  - Recall@class:  did at least one generated test FAIL on the buggy
                   variant? (per docs/project_plan.md § 5)
  - Precision:     did all generated tests PASS on the clean variant?

Both measurements re-use `validator.run.run_on_clean` to invoke the
Java runner-helper — one helper, two callers (the validator-gate and
us). The function name is misleading for the buggy invocation;
semantically it's just "compile + run this test class against this
target", which is what we need.

Modes:
  - "pipeline" (default): runs `pipeline.run` (analyzer -> generator
    -> validator -> aggregator). Pipeline drops failing tests, so we
    only see surviving methods.
  - "baseline": runs `synthesize_baseline` (one Sonnet call, no
    analyzer/retrieval/per-risk loop, no validator gate). Output is
    raw — parse / compile / run-on-clean failures are tracked as
    distinct row statuses (baseline_unparseable / baseline_compile_fail
    / baseline_clean_fail) so the comparison report can call them out
    rather than silently zeroing recall.

Run from `engine/`:

    py -3.13 eval/runner.py              # pipeline mode (default)
    py -3.13 eval/runner.py --baseline   # baseline mode

Writes one timestamped JSON file under `eval/results/` per run named
`run-{mode}-<timestamp>.json` and prints a one-line summary to stdout.

Layering note: this module sits under `eval/`, not `src/agenttest/`.
The pipeline depends on `agenttest.*` only; the eval harness depends
on both `agenttest.*` AND on local `eval/injections`. That's fine —
the arrow is one-directional (eval -> agenttest), and `eval/` is
offline analysis tooling, not request-path code.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml

ENGINE_ROOT = Path(__file__).resolve().parent.parent
# `eval/` is a sibling of `src/`, not a package under `agenttest`; make
# `eval.injections` importable for both this module (when run as a
# script) and the integration tests.
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from agenttest import pipeline  # noqa: E402
from agenttest.agents.factory import AgentClientFactory  # noqa: E402
from agenttest.agents.role import AgentRole  # noqa: E402
from agenttest.baseline.synthesize import synthesize_baseline  # noqa: E402
from agenttest.config import settings  # noqa: E402
from agenttest.validator.run import run_on_clean  # noqa: E402
from eval.injections import INJECTIONS_BY_NAME  # noqa: E402
from eval.results import EvalResult, SampleResult, SampleStatus, SummaryStats  # noqa: E402

logger = logging.getLogger(__name__)

EvalMode = Literal[
    "pipeline-full",            # analyzer + OWASP retrieval + validator gate
    "pipeline-no-retrieval",    # analyzer, no retrieval, validator gate ON
    "pipeline-analyzer-only",   # analyzer, no retrieval, NO validator gate
    "baseline",                 # single-prompt, no analyzer/retrieval/validator
]


# Map an ablation mode to the pipeline.run flags it implies. Baseline
# is excluded — it routes through `_measure_pair_baseline`, not pipeline.run.
_PIPELINE_MODE_KWARGS: dict[str, dict[str, bool]] = {
    "pipeline-full":           {"use_owasp_retrieval": True,  "use_validator_gate": True},
    "pipeline-no-retrieval":   {"use_owasp_retrieval": False, "use_validator_gate": True},
    "pipeline-analyzer-only":  {"use_owasp_retrieval": False, "use_validator_gate": False},
}


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
    name = f"{target_class}AgentGenTest"
    return f"{target_package}.{name}" if target_package else name


def _summarize(results: list[SampleResult]) -> SummaryStats:
    total = len(results)
    measured = [r for r in results if r.status == "measured"]
    n_measured = len(measured)
    no_tests = sum(1 for r in results if r.status == "no_tests_emitted")
    errors = sum(1 for r in results if r.status == "pipeline_error")
    bl_unparseable = sum(1 for r in results if r.status == "baseline_unparseable")
    bl_compile_fail = sum(1 for r in results if r.status == "baseline_compile_fail")
    bl_clean_fail = sum(1 for r in results if r.status == "baseline_clean_fail")

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
        baseline_unparseable=bl_unparseable,
        baseline_compile_fail=bl_compile_fail,
        baseline_clean_fail=bl_clean_fail,
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


def _baseline_audit_row(
    sample_id: str,
    injection_name: str,
    status: SampleStatus,
    clean_outcome: str | None = None,
) -> SampleResult:
    """Row for a baseline-mode pair that produced output but didn't reach
    a measurable state (unparseable / compile_fail / clean_fail).

    These rows are tracked separately in SummaryStats so they don't
    distort recall / precision but the comparison report can still
    call them out — see eval/results.py for the rationale.
    """
    return SampleResult(
        sample_id=sample_id,
        injection_name=injection_name,
        status=status,
        tests_emitted=0 if status == "baseline_unparseable" else 1,
        refused_sites=0,
        clean_outcome=clean_outcome,
        buggy_outcome=None,
        recall_caught=False,
        precision_clean_pass=False,
        error=None,
    )


async def _run_clean_and_buggy(
    *,
    clean_java_path: Path,
    buggy_source: str,
    target_class: str,
    test_class_source: str,
    test_fqn: str,
):
    """Run the same test class against (clean, buggy) target variants in parallel.

    Returns (clean_result, buggy_result). Raises whichever subprocess
    exception occurred — caller's broad try/except converts to a
    pipeline_error row.

    Both invocations are sync subprocess calls; off-loaded to threads
    so we don't stall the event loop. `return_exceptions=True` on the
    gather ensures both threads reach completion before the tempdir
    is reaped — otherwise an exception from one subprocess could exit
    the `with` while the other JVM still holds the buggy file open
    (Windows would then fail the rmtree).
    """
    with tempfile.TemporaryDirectory(prefix="agenttest-eval-buggy-") as buggy_dir:
        buggy_path = Path(buggy_dir) / f"{target_class}.java"
        buggy_path.write_text(buggy_source, encoding="utf-8")

        results = await asyncio.gather(
            asyncio.to_thread(
                run_on_clean,
                target_class_path=clean_java_path,
                test_class_source=test_class_source,
                test_class_fqn=test_fqn,
            ),
            asyncio.to_thread(
                run_on_clean,
                target_class_path=buggy_path,
                test_class_source=test_class_source,
                test_class_fqn=test_fqn,
            ),
            return_exceptions=True,
        )
    clean_result, buggy_result = results
    for r in (clean_result, buggy_result):
        if isinstance(r, BaseException):
            raise r
    return clean_result, buggy_result


async def _measure_pair(
    sample_id: str,
    injection_name: str,
    clean_java_path: Path,
    test_fqn: str,
    target_class: str,
    pipeline_kwargs: dict[str, bool] | None = None,
) -> SampleResult:
    """Run the pipeline + recall + precision for one (sample, injection).

    `pipeline_kwargs` controls the ablation row — see
    `_PIPELINE_MODE_KWARGS`. Defaults to the full pipeline.

    The whole body sits inside one broad try/except. **This is the only
    place a bare `except Exception:` is acceptable in the codebase**,
    because the eval runner is offline analysis tooling and one broken
    pair must not abort the whole run. The error is recorded per-pair
    via `status="pipeline_error"`.
    """
    pipeline_kwargs = pipeline_kwargs or _PIPELINE_MODE_KWARGS["pipeline-full"]
    try:
        emission = await pipeline.run(clean_java_path, **pipeline_kwargs)

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

        # Precision: clean source, generated tests should all PASS.
        # Recall:    buggy source, at least one generated test should FAIL.
        clean_result, buggy_result = await _run_clean_and_buggy(
            clean_java_path=clean_java_path,
            buggy_source=buggy_source,
            target_class=target_class,
            test_class_source=emission.java_source,
            test_fqn=test_fqn,
        )

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


async def _measure_pair_baseline(
    sample_id: str,
    injection_name: str,
    clean_java_path: Path,
    test_fqn: str,
    target_class: str,
    target_package: str,
    baseline_client,
) -> SampleResult:
    """Baseline-mode counterpart to `_measure_pair`.

    Calls `synthesize_baseline` (one Sonnet call) instead of running
    the full pipeline. Branches on three pre-recall failure modes
    distinct to baseline (parse fail / compile fail / fail-on-clean)
    so they show up as their own row statuses rather than collapsing
    into recall=0.

    Same broad-except-Exception contract as `_measure_pair` — one
    broken pair must not abort the run.
    """
    try:
        clean_source = clean_java_path.read_text(encoding="utf-8")
        emission = await synthesize_baseline(
            java_source=clean_source,
            target_class_name=target_class,
            target_package=target_package,
            client=baseline_client,
        )

        if not emission.parseable:
            return _baseline_audit_row(
                sample_id, injection_name, status="baseline_unparseable"
            )

        injection_cls = INJECTIONS_BY_NAME.get(injection_name)
        if injection_cls is None:
            raise ValueError(f"unknown injection: {injection_name!r}")
        buggy_source = injection_cls().apply(clean_source)

        clean_result, buggy_result = await _run_clean_and_buggy(
            clean_java_path=clean_java_path,
            buggy_source=buggy_source,
            target_class=target_class,
            test_class_source=emission.java_source,
            test_fqn=test_fqn,
        )

        if clean_result.outcome == "COMPILE_FAIL":
            return _baseline_audit_row(
                sample_id,
                injection_name,
                status="baseline_compile_fail",
                clean_outcome=clean_result.outcome,
            )
        if clean_result.outcome == "FAIL":
            return _baseline_audit_row(
                sample_id,
                injection_name,
                status="baseline_clean_fail",
                clean_outcome=clean_result.outcome,
            )

        # PASS on clean → measure recall on buggy.
        return SampleResult(
            sample_id=sample_id,
            injection_name=injection_name,
            status="measured",
            tests_emitted=1,
            refused_sites=0,
            clean_outcome=clean_result.outcome,
            buggy_outcome=buggy_result.outcome,
            recall_caught=buggy_result.outcome == "FAIL",
            precision_clean_pass=True,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "[eval-baseline] error on %s / %s", sample_id, injection_name
        )
        return _error_row(sample_id, injection_name, f"{type(exc).__name__}: {exc}")


async def run_eval(
    samples_dir: Path = Path("eval/samples"),
    results_dir: Path = Path("eval/results"),
    mode: EvalMode = "pipeline-full",
) -> EvalResult:
    """Run the eval harness across every (sample, applicable injection) pair.

    Modes (S4 ablation matrix):
      - `pipeline-full`: analyzer + OWASP retrieval + validator gate.
      - `pipeline-no-retrieval`: analyzer + raw site, no OWASP retrieval,
        validator gate still applied. Tests "does OWASP retrieval help
        on top of the gate?"
      - `pipeline-analyzer-only`: analyzer + raw site, no validator
        gate. Tests "does the validator gate help on top of analyzer?"
      - `baseline`: single Sonnet call, no analyzer/retrieval/validator.

    Paths default to relative `eval/...`, matching the README's
    instructions to invoke from `engine/`. They're resolved against
    the current working directory, so callers can pass absolute paths
    if they prefer.
    """
    samples_dir = samples_dir.resolve()
    results_dir = results_dir.resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    meta_paths = sorted(samples_dir.glob("**/*.meta.yaml"))
    logger.info(
        "[eval:%s] discovered %d sample(s) under %s",
        mode, len(meta_paths), samples_dir,
    )

    # Baseline mode needs a BASELINE-role client; pipeline mode is
    # self-contained (pipeline.run constructs its own factory).
    factory: AgentClientFactory | None = None
    baseline_client = None
    if mode == "baseline":
        factory = AgentClientFactory.from_settings(settings)
        baseline_client = factory.get(AgentRole.BASELINE)

    rows: list[SampleResult] = []
    try:
        for meta_path in meta_paths:
            meta = _load_meta(meta_path)
            sample_id = meta["sample_id"]
            target_class = meta["target_class"]
            target_package = meta["target_package"] or ""
            injections = meta["applicable_injections"] or []

            clean_java_path = _resolve_clean_java_path(meta_path, target_class)
            test_fqn = _test_fqn(target_package, target_class)

            for injection_name in injections:
                logger.info(
                    "[eval:%s] running %s / %s", mode, sample_id, injection_name
                )
                if mode == "baseline":
                    assert baseline_client is not None  # narrowed by mode check above
                    row = await _measure_pair_baseline(
                        sample_id=sample_id,
                        injection_name=injection_name,
                        clean_java_path=clean_java_path,
                        test_fqn=test_fqn,
                        target_class=target_class,
                        target_package=target_package,
                        baseline_client=baseline_client,
                    )
                else:
                    row = await _measure_pair(
                        sample_id=sample_id,
                        injection_name=injection_name,
                        clean_java_path=clean_java_path,
                        test_fqn=test_fqn,
                        target_class=target_class,
                        pipeline_kwargs=_PIPELINE_MODE_KWARGS[mode],
                    )
                rows.append(row)
    finally:
        if factory is not None:
            await factory.aclose()

    now = datetime.now(UTC)
    summary = _summarize(rows)
    result = EvalResult(
        timestamp_utc=now.isoformat(),
        samples=rows,
        summary=summary,
    )

    out_path = results_dir / f"run-{mode}-{_filesystem_safe_timestamp(now)}.json"
    out_path.write_text(
        json.dumps(asdict(result), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    print(
        f"Eval complete ({mode}): {summary.measured_pairs}/{summary.total_pairs} "
        f"measured pairs | "
        f"Recall@class={summary.recall_at_class * 100:.1f}% | "
        f"Precision={summary.precision * 100:.1f}%"
    )
    if mode == "baseline":
        print(
            f"  baseline audit: unparseable={summary.baseline_unparseable} "
            f"compile_fail={summary.baseline_compile_fail} "
            f"clean_fail={summary.baseline_clean_fail}"
        )
    try:
        rel = out_path.relative_to(Path.cwd())
        print(f"Results: {rel}")
    except ValueError:
        print(f"Results: {out_path}")

    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AgentTest eval runner (pipeline ablation modes + baseline)."
    )
    parser.add_argument(
        "--mode",
        choices=[
            "pipeline-full",
            "pipeline-no-retrieval",
            "pipeline-analyzer-only",
            "baseline",
        ],
        default="pipeline-full",
        help="Ablation row to run. Default: pipeline-full (analyzer + OWASP + validator).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(run_eval(mode=args.mode))
