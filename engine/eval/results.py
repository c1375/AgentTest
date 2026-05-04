"""Result dataclasses for the eval harness.

Internal to `engine/eval/`; not part of the pipeline contract surface
(`agenttest.contracts`). The pipeline contracts describe handoffs
between stages; these describe the eval runner's per-(sample,injection)
measurement and the aggregate run summary.

A `SampleResult` is one row in the run JSON: one sample paired with
one named injection. `EvalResult` is the file-level shape written to
`eval/results/run-{mode}-<timestamp>.json` (mode = pipeline | baseline).

`status` enumerates the ways a pair can finish:

  Common to both modes:
    - "measured":            test executed against both clean and buggy
                             variants; recall/precision are valid.
    - "no_tests_emitted":    the pipeline ran cleanly but yielded no
                             surviving JUnit methods (pipeline mode only
                             in practice — baseline always emits
                             *something*, even if unparseable).
    - "pipeline_error":      a stage raised. The exception is captured
                             in `error` and the runner-helper is skipped.

  Baseline-mode-only failure breakdowns (per Q2 in the Step 5 design
  discussion: baseline failures get their own audit categories rather
  than collapsing into recall/precision math):
    - "baseline_unparseable":   model output failed javalang parse.
    - "baseline_compile_fail":  parses but the wrapped class doesn't
                                compile against the runner-helper
                                classpath (e.g., Mockito imports despite
                                the prompt's no-Mockito constraint).
    - "baseline_clean_fail":    compiles but at least one test FAILs
                                on the clean variant (asserts a false
                                invariant).

  Recall / precision denominators are still `measured_pairs` only —
  the baseline-* statuses are separate counters in `SummaryStats` so
  the comparison report can call out "baseline emits N% un-compilable
  tests" as a distinct signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SampleStatus = Literal[
    "measured",
    "no_tests_emitted",
    "pipeline_error",
    "baseline_unparseable",
    "baseline_compile_fail",
    "baseline_clean_fail",
]


@dataclass(frozen=True)
class SampleResult:
    """One eval row: a sample paired with one named injection."""

    sample_id: str
    injection_name: str
    status: SampleStatus
    tests_emitted: int
    refused_sites: int
    clean_outcome: str | None
    buggy_outcome: str | None
    recall_caught: bool
    precision_clean_pass: bool
    error: str | None


@dataclass(frozen=True)
class SummaryStats:
    """Run-level rollup. Recall/precision denominators are `measured_pairs`.

    Baseline-only counters default to 0 in pipeline-mode runs so the
    JSON shape is uniform across both modes.
    """

    total_pairs: int
    measured_pairs: int
    recall_at_class: float
    precision: float
    no_tests_emitted: int
    pipeline_errors: int
    baseline_unparseable: int = 0
    baseline_compile_fail: int = 0
    baseline_clean_fail: int = 0


@dataclass(frozen=True)
class EvalResult:
    """One full eval run."""

    timestamp_utc: str
    samples: list[SampleResult]
    summary: SummaryStats


@dataclass(frozen=True)
class ComparisonDelta:
    """Pipeline-mode metric minus baseline-mode metric, in percentage points.

    Positive numbers mean the structured pipeline beat the single-prompt
    baseline. `samples_compared` is `min(pipeline.total_pairs,
    baseline.total_pairs)` — they should be equal in practice (same
    samples_dir, same applicable_injections), but mismatched counts are
    a configuration bug worth surfacing rather than silently averaging.
    """
    recall_at_class_pp: float
    precision_pp: float
    samples_compared: int


@dataclass(frozen=True)
class ComparisonResult:
    """Output of `eval/compare.py`. Combines both modes' EvalResults
    plus a delta. Headline artifact for the Week-6 check-in narrative.
    """
    timestamp_utc: str
    pipeline: EvalResult
    baseline: EvalResult
    delta: ComparisonDelta
