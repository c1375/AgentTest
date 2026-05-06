"""Combined 4-row ablation run.

Runs each pipeline ablation row + baseline back-to-back on the same
samples and emits one `ablation-<timestamp>.json` carrying all four
EvalResults plus adjacent-row deltas. This is the headline artifact
for the Week-7 (S4) check-in narrative.

Stdout summary is the grader-facing one-line readout per row, plus
the three deltas (component-by-component). The JSON has every
per-(sample, injection) row from each mode.

Layering note: this is offline analysis tooling sitting under
`engine/eval/`, parallel to `runner.py` and `compare.py`. It depends
on `eval.runner` (which imports `agenttest.*` for both pipeline and
baseline paths) plus the `Ablation*` dataclasses from `eval.results`.

Run from `engine/`:

    py -3.13 eval/ablation.py

Cost: 4 rows × N samples. With N=15 and current Sonnet pricing,
roughly $8-12 per invocation (3 pipeline rows × ~1.3 risks/sample ×
$0.07 + 1 baseline row × $0.20/sample at 8192 max_tokens). Per
docs/plan/sprint-4.md the S4 cumulative cap is $40 — at this
per-run cost there's headroom for ~3 iterations.

Row order is simplest → fullest so each adjacent-row delta isolates
exactly one added component:

    baseline                      → pipeline-analyzer-only   adds: analyzer + risk-targeted prompt
    pipeline-analyzer-only        → pipeline-no-retrieval    adds: validator gate
    pipeline-no-retrieval         → pipeline-full            adds: OWASP catalog retrieval
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
    AblationDelta,
    AblationResult,
    AblationRow,
)
from eval.runner import (  # noqa: E402
    EvalMode,
    _filesystem_safe_timestamp,
    run_eval,
)

logger = logging.getLogger(__name__)


# Simplest → fullest. Each adjacent pair adds one component.
ABLATION_ROW_ORDER: tuple[EvalMode, ...] = (
    "baseline",
    "pipeline-analyzer-only",
    "pipeline-no-retrieval",
    "pipeline-full",
)


_COMPONENT_ADDED: dict[tuple[EvalMode, EvalMode], str] = {
    ("baseline", "pipeline-analyzer-only"):
        "analyzer + risk-targeted prompt",
    ("pipeline-analyzer-only", "pipeline-no-retrieval"):
        "validator gate",
    ("pipeline-no-retrieval", "pipeline-full"):
        "OWASP catalog retrieval",
}


def _pp(a: float, b: float) -> float:
    """Percentage-point delta of two ratios in [0, 1], rounded to 1 dp."""
    return round((a - b) * 100, 1)


def compute_deltas(rows: list[AblationRow]) -> list[AblationDelta]:
    """Adjacent-row deltas in matrix order.

    For 4 rows we get 3 deltas — each isolating one added component.
    If the rows list is in the wrong order or has gaps,
    `_COMPONENT_ADDED` will fall back to a literal mode-pair label so
    the output is still readable; that's a misconfig signal not a
    crash.
    """
    deltas: list[AblationDelta] = []
    for simpler, fuller in zip(rows, rows[1:]):
        component = _COMPONENT_ADDED.get(
            (simpler.mode, fuller.mode),  # type: ignore[arg-type]
            f"{simpler.mode} → {fuller.mode}",
        )
        deltas.append(AblationDelta(
            simpler_mode=simpler.mode,
            fuller_mode=fuller.mode,
            component_added=component,
            recall_at_class_pp=_pp(
                fuller.result.summary.recall_at_class,
                simpler.result.summary.recall_at_class,
            ),
            precision_pp=_pp(
                fuller.result.summary.precision,
                simpler.result.summary.precision,
            ),
        ))
    return deltas


async def run_ablation(
    samples_dir: Path = Path("eval/samples"),
    results_dir: Path = Path("eval/results"),
) -> AblationResult:
    """Run all 4 ablation rows in matrix order and write ablation.json."""
    samples_dir = samples_dir.resolve()
    results_dir = results_dir.resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    rows: list[AblationRow] = []
    for mode in ABLATION_ROW_ORDER:
        logger.info("[ablation] running %s", mode)
        result = await run_eval(
            samples_dir=samples_dir, results_dir=results_dir, mode=mode
        )
        rows.append(AblationRow(mode=mode, result=result))

    now = datetime.now(UTC)
    deltas = compute_deltas(rows)
    ablation = AblationResult(
        timestamp_utc=now.isoformat(),
        rows=rows,
        deltas=deltas,
    )

    out_path = results_dir / f"ablation-{_filesystem_safe_timestamp(now)}.json"
    out_path.write_text(
        json.dumps(asdict(ablation), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    print()
    print(f"Ablation complete: {len(rows)} rows on the same sample set")
    for r in rows:
        s = r.result.summary
        print(
            f"  {r.mode:28} "
            f"Recall@class={s.recall_at_class * 100:5.1f}% "
            f"| Precision={s.precision * 100:5.1f}% "
            f"| Ship-bad={s.ship_bad_tests_rate * 100:5.1f}% "
            f"| measured={s.measured_pairs}/{s.total_pairs}"
        )
    print()
    print("Component-added deltas (fuller minus simpler, in pp):")
    for d in deltas:
        print(
            f"  + {d.component_added:35} "
            f"recall {d.recall_at_class_pp:+.1f} | precision {d.precision_pp:+.1f}"
        )

    try:
        rel = out_path.relative_to(Path.cwd())
        print(f"\nResults: {rel}")
    except ValueError:
        print(f"\nResults: {out_path}")

    return ablation


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(run_ablation())
