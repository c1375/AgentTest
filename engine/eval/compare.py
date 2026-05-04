"""Combined pipeline-vs-baseline comparison run.

Runs the eval harness in both modes back-to-back on the same samples
and emits one `comparison-<timestamp>.json` carrying both modes'
rollups plus a percentage-point delta. This is the headline artifact
for the Week-6 check-in narrative.

Stdout summary is the grader-facing one-line readout — read it first,
dig into the JSON for per-pair details.

Layering note: this is offline analysis tooling sitting under
`engine/eval/`, parallel to `runner.py`. It depends on `eval.runner`
(which imports `agenttest.*` for both pipeline and baseline paths)
plus the `ComparisonDelta` / `ComparisonResult` dataclasses from
`eval.results`.

Run from `engine/`:

    py -3.13 eval/compare.py

Cost: one full pipeline pass + one full baseline pass against every
sample in `eval/samples/`. With 6 samples and current Sonnet pricing,
expect roughly $0.50–$1.00 per invocation. See
`docs/plan/sprint-3.md` § "Step 6" for the design rationale.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from eval.results import (  # noqa: E402
    ComparisonDelta,
    ComparisonResult,
    EvalResult,
)
from eval.runner import _filesystem_safe_timestamp, run_eval  # noqa: E402

logger = logging.getLogger(__name__)


def _pp(a: float, b: float) -> float:
    """Percentage-point delta of two ratios in [0, 1], rounded to 1 dp."""
    return round((a - b) * 100, 1)


def compute_delta(pipeline: EvalResult, baseline: EvalResult) -> ComparisonDelta:
    """Compute the pipeline-minus-baseline delta in percentage points.

    `samples_compared` uses `min(...)` defensively: if the two modes
    iterated different sample counts (which would itself be a bug,
    since they share `samples_dir` + the same meta files), the smaller
    number is the only fair denominator.
    """
    return ComparisonDelta(
        recall_at_class_pp=_pp(
            pipeline.summary.recall_at_class, baseline.summary.recall_at_class
        ),
        precision_pp=_pp(
            pipeline.summary.precision, baseline.summary.precision
        ),
        samples_compared=min(
            pipeline.summary.total_pairs, baseline.summary.total_pairs
        ),
    )


async def run_comparison(
    samples_dir: Path = Path("eval/samples"),
    results_dir: Path = Path("eval/results"),
) -> ComparisonResult:
    """Run pipeline mode, then baseline mode, then write comparison.json.

    Both modes also write their own per-mode `run-{mode}-<ts>.json`
    files via `run_eval` — those are the raw audit data; the
    comparison file is the rollup that links them with a delta.

    Pipeline runs first because it's slower (analyzer + retrieval +
    validator gate per site) and a baseline-first ordering would mean
    a pipeline failure aborts after we've already paid for the
    baseline LLM calls. Pipeline-first means a failure mid-run loses
    only the pipeline cost.
    """
    samples_dir = samples_dir.resolve()
    results_dir = results_dir.resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[compare] running pipeline mode")
    pipeline_result = await run_eval(
        samples_dir=samples_dir, results_dir=results_dir, mode="pipeline"
    )

    logger.info("[compare] running baseline mode")
    baseline_result = await run_eval(
        samples_dir=samples_dir, results_dir=results_dir, mode="baseline"
    )

    now = datetime.now(UTC)
    delta = compute_delta(pipeline_result, baseline_result)
    result = ComparisonResult(
        timestamp_utc=now.isoformat(),
        pipeline=pipeline_result,
        baseline=baseline_result,
        delta=delta,
    )

    out_path = results_dir / f"comparison-{_filesystem_safe_timestamp(now)}.json"
    out_path.write_text(
        json.dumps(asdict(result), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    print()
    print(f"Comparison complete: {delta.samples_compared} pairs each")
    print(
        f"  Pipeline: Recall@class={pipeline_result.summary.recall_at_class * 100:.1f}% "
        f"| Precision={pipeline_result.summary.precision * 100:.1f}%"
    )
    print(
        f"  Baseline: Recall@class={baseline_result.summary.recall_at_class * 100:.1f}% "
        f"| Precision={baseline_result.summary.precision * 100:.1f}%"
    )
    bl_audit = (
        f"unparseable={baseline_result.summary.baseline_unparseable} "
        f"compile_fail={baseline_result.summary.baseline_compile_fail} "
        f"clean_fail={baseline_result.summary.baseline_clean_fail}"
    )
    print(f"  (baseline audit: {bl_audit})")
    print(
        f"  Delta:    {delta.recall_at_class_pp:+.1f} pp recall "
        f"| {delta.precision_pp:+.1f} pp precision"
    )

    try:
        rel = out_path.relative_to(Path.cwd())
        print(f"Results: {rel}")
    except ValueError:
        print(f"Results: {out_path}")

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(run_comparison())
