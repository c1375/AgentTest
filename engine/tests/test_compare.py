"""Tests for eval/compare.py.

Two flavors:

1. Unit tests on `compute_delta`: synthetic EvalResults with known
   summary stats drive the percentage-point math. No LLM, no JVM.

2. Integration test on `run_comparison`: monkey-patches `run_eval`
   to return canned EvalResults, then asserts the comparison.json
   shape + headline. No real LLM call, no JVM.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from eval.compare import compute_delta, run_comparison  # noqa: E402
from eval.results import (  # noqa: E402
    ComparisonDelta,
    EvalResult,
    SampleResult,
    SummaryStats,
)


def _result(
    *,
    recall: float,
    precision: float,
    total_pairs: int,
    measured_pairs: int | None = None,
    baseline_unparseable: int = 0,
    baseline_compile_fail: int = 0,
    baseline_clean_fail: int = 0,
) -> EvalResult:
    """Build a minimal EvalResult fixture for the comparison math."""
    measured = measured_pairs if measured_pairs is not None else total_pairs
    return EvalResult(
        timestamp_utc="2026-05-04T00:00:00+00:00",
        samples=[],
        summary=SummaryStats(
            total_pairs=total_pairs,
            measured_pairs=measured,
            recall_at_class=recall,
            precision=precision,
            no_tests_emitted=0,
            pipeline_errors=0,
            baseline_unparseable=baseline_unparseable,
            baseline_compile_fail=baseline_compile_fail,
            baseline_clean_fail=baseline_clean_fail,
        ),
    )


# ---------------------------------------------------------------------------
# compute_delta (unit)
# ---------------------------------------------------------------------------


class TestComputeDelta:
    def test_pipeline_beats_baseline_by_50pp_recall(self) -> None:
        delta = compute_delta(
            pipeline=_result(recall=1.0, precision=1.0, total_pairs=6),
            baseline=_result(recall=0.5, precision=1.0, total_pairs=6),
        )
        assert delta.recall_at_class_pp == 50.0
        assert delta.precision_pp == 0.0
        assert delta.samples_compared == 6

    def test_baseline_beats_pipeline_yields_negative_delta(self) -> None:
        """The project narrative anchors on honesty: a negative delta is
        the empirical answer too, and compute_delta surfaces it as-is."""
        delta = compute_delta(
            pipeline=_result(recall=0.3, precision=1.0, total_pairs=6),
            baseline=_result(recall=0.6, precision=1.0, total_pairs=6),
        )
        assert delta.recall_at_class_pp == -30.0

    def test_samples_compared_uses_min_when_counts_diverge(self) -> None:
        """If the two modes iterated different sample counts (a config
        bug), `samples_compared` reflects the smaller — making the
        mismatch obvious in the JSON rather than silent-averaging."""
        delta = compute_delta(
            pipeline=_result(recall=1.0, precision=1.0, total_pairs=6),
            baseline=_result(recall=1.0, precision=1.0, total_pairs=4),
        )
        assert delta.samples_compared == 4

    def test_rounding_to_one_decimal_place(self) -> None:
        """Recall=2/3 vs 1/3 → 33.333… pp, rounds to 33.3."""
        delta = compute_delta(
            pipeline=_result(recall=2 / 3, precision=1.0, total_pairs=6),
            baseline=_result(recall=1 / 3, precision=1.0, total_pairs=6),
        )
        assert delta.recall_at_class_pp == 33.3

    def test_precision_delta_independent_of_recall(self) -> None:
        delta = compute_delta(
            pipeline=_result(recall=0.5, precision=0.9, total_pairs=6),
            baseline=_result(recall=0.5, precision=0.7, total_pairs=6),
        )
        assert delta.recall_at_class_pp == 0.0
        assert delta.precision_pp == 20.0


# ---------------------------------------------------------------------------
# run_comparison (integration with mocked run_eval)
# ---------------------------------------------------------------------------


async def test_run_comparison_emits_comparison_file_with_both_modes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """run_comparison wires pipeline + baseline EvalResults into one
    comparison-<ts>.json, computes the delta, and prints the headline."""
    pipeline_fixture = _result(recall=1.0, precision=1.0, total_pairs=6)
    baseline_fixture = _result(
        recall=0.5,
        precision=1.0,
        total_pairs=6,
        measured_pairs=4,  # 2 pairs hit baseline_compile_fail
        baseline_compile_fail=2,
    )

    fake_run_eval = AsyncMock(side_effect=[pipeline_fixture, baseline_fixture])
    monkeypatch.setattr("eval.compare.run_eval", fake_run_eval)

    samples_dir = tmp_path / "samples"
    samples_dir.mkdir()
    results_dir = tmp_path / "results"

    comparison = await run_comparison(
        samples_dir=samples_dir, results_dir=results_dir
    )

    # Both modes were invoked, in pipeline-then-baseline order.
    assert fake_run_eval.await_count == 2
    first_mode = fake_run_eval.await_args_list[0].kwargs.get("mode", "pipeline-full")
    second_mode = fake_run_eval.await_args_list[1].kwargs.get("mode")
    assert first_mode == "pipeline-full"
    assert second_mode == "baseline"

    # The returned ComparisonResult carries both EvalResults verbatim.
    assert comparison.pipeline is pipeline_fixture
    assert comparison.baseline is baseline_fixture
    assert comparison.delta == ComparisonDelta(
        recall_at_class_pp=50.0,
        precision_pp=0.0,
        samples_compared=6,
    )

    # The on-disk JSON file matches the dataclass dump.
    out_files = list(results_dir.glob("comparison-*.json"))
    assert len(out_files) == 1, (
        f"expected one comparison-*.json, got {[p.name for p in results_dir.iterdir()]}"
    )
    payload = json.loads(out_files[0].read_text(encoding="utf-8"))
    assert payload["delta"]["recall_at_class_pp"] == 50.0
    assert payload["pipeline"]["summary"]["recall_at_class"] == 1.0
    assert payload["baseline"]["summary"]["recall_at_class"] == 0.5
    assert payload["baseline"]["summary"]["baseline_compile_fail"] == 2


async def test_run_comparison_propagates_exceptions_from_run_eval(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """A failure in pipeline mode aborts before baseline mode runs.

    Per compare.py docstring: pipeline-first ordering means a failure
    only loses the pipeline cost, not also the baseline cost.
    """
    pipeline_err = RuntimeError("pipeline blew up")
    fake_run_eval = AsyncMock(side_effect=pipeline_err)
    monkeypatch.setattr("eval.compare.run_eval", fake_run_eval)

    import pytest

    with pytest.raises(RuntimeError, match="pipeline blew up"):
        await run_comparison(
            samples_dir=tmp_path / "samples",
            results_dir=tmp_path / "results",
        )
    # Baseline must NOT have been called once pipeline failed.
    assert fake_run_eval.await_count == 1
