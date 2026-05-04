"""Result dataclasses for the eval harness.

Internal to `engine/eval/`; not part of the pipeline contract surface
(`agenttest.contracts`). The pipeline contracts describe handoffs
between stages; these describe the eval runner's per-(sample,injection)
measurement and the aggregate run summary.

A `SampleResult` is one row in the run JSON: one sample paired with
one named injection. `EvalResult` is the file-level shape written to
`eval/results/run-<timestamp>.json`.

`status` is a tri-state because an eval pair can fail to produce a
measurement in two distinct ways:
  - "no_tests_emitted": the pipeline ran cleanly but yielded no
    surviving JUnit methods, so there's nothing to run against the
    clean / buggy variants.
  - "pipeline_error": the pipeline raised. We capture the stringified
    exception and skip the runner-helper invocations for this pair.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SampleStatus = Literal["measured", "no_tests_emitted", "pipeline_error"]


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
    """Run-level rollup. Recall/precision denominators are `measured_pairs`."""

    total_pairs: int
    measured_pairs: int
    recall_at_class: float
    precision: float
    no_tests_emitted: int
    pipeline_errors: int


@dataclass(frozen=True)
class EvalResult:
    """One full eval run."""

    timestamp_utc: str
    samples: list[SampleResult]
    summary: SummaryStats
