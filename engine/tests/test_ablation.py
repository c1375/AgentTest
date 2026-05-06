"""Tests for eval/ablation.py.

Two flavors mirroring test_compare.py:

1. Unit tests on `compute_deltas`: synthetic AblationRows drive the
   adjacent-row pp math + component-added labels. No LLM, no JVM.

2. Integration test on `run_ablation`: monkey-patches `run_eval` to
   return canned EvalResults, asserts ablation-{ts}.json shape and
   the 4-row × 3-delta structure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from eval.ablation import (  # noqa: E402
    ABLATION_ROW_ORDER,
    compute_deltas,
    run_ablation,
)
from eval.results import (  # noqa: E402
    AblationRow,
    EvalResult,
    SummaryStats,
)


def _result(*, recall: float, precision: float, total_pairs: int = 6) -> EvalResult:
    return EvalResult(
        timestamp_utc="2026-05-06T00:00:00+00:00",
        samples=[],
        summary=SummaryStats(
            total_pairs=total_pairs,
            measured_pairs=total_pairs,
            recall_at_class=recall,
            precision=precision,
            no_tests_emitted=0,
            pipeline_errors=0,
        ),
    )


def _row(mode: str, recall: float, precision: float = 1.0) -> AblationRow:
    return AblationRow(mode=mode, result=_result(recall=recall, precision=precision))


# ---------------------------------------------------------------------------
# compute_deltas (unit)
# ---------------------------------------------------------------------------


class TestComputeDeltas:
    def test_three_deltas_for_four_rows(self) -> None:
        rows = [
            _row("baseline",                0.30),
            _row("pipeline-analyzer-only",  0.50),
            _row("pipeline-no-retrieval",   0.60),
            _row("pipeline-full",           0.80),
        ]
        deltas = compute_deltas(rows)
        assert len(deltas) == 3

    def test_each_delta_isolates_one_added_component(self) -> None:
        rows = [
            _row("baseline",                0.30),
            _row("pipeline-analyzer-only",  0.50),
            _row("pipeline-no-retrieval",   0.60),
            _row("pipeline-full",           0.80),
        ]
        deltas = compute_deltas(rows)
        # Adjacent-pair labels are pre-mapped in _COMPONENT_ADDED so the
        # JSON is human-readable without the reader needing to consult
        # this test.
        assert deltas[0].component_added == "analyzer + risk-targeted prompt"
        assert deltas[1].component_added == "validator gate"
        assert deltas[2].component_added == "OWASP catalog retrieval"

    def test_delta_pp_math(self) -> None:
        rows = [
            _row("baseline",                0.30, precision=0.5),
            _row("pipeline-analyzer-only",  0.50, precision=0.7),
        ]
        deltas = compute_deltas(rows)
        assert deltas[0].recall_at_class_pp == 20.0
        assert deltas[0].precision_pp == 20.0

    def test_negative_delta_surfaced_as_is(self) -> None:
        """A row that hurts recall vs the simpler row gets a negative
        delta — the ablation is honest about regressions."""
        rows = [
            _row("baseline",                0.60),
            _row("pipeline-analyzer-only",  0.40),
        ]
        deltas = compute_deltas(rows)
        assert deltas[0].recall_at_class_pp == -20.0

    def test_unknown_mode_pair_falls_back_to_arrow_label(self) -> None:
        """If rows are out of order or contain an unrecognized mode,
        component_added falls back to a literal pair label so the
        output stays readable rather than crashing."""
        rows = [
            _row("baseline",     0.30),
            _row("mystery-mode", 0.50),
        ]
        deltas = compute_deltas(rows)
        assert deltas[0].component_added == "baseline → mystery-mode"

    def test_empty_rows_yields_empty_deltas(self) -> None:
        assert compute_deltas([]) == []

    def test_single_row_yields_empty_deltas(self) -> None:
        rows = [_row("baseline", 0.5)]
        assert compute_deltas(rows) == []


# ---------------------------------------------------------------------------
# run_ablation (integration with mocked run_eval)
# ---------------------------------------------------------------------------


async def test_run_ablation_invokes_all_four_modes_in_matrix_order(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """run_ablation calls run_eval once per row in ABLATION_ROW_ORDER
    and threads the mode through. The output ablation-<ts>.json
    contains 4 rows + 3 deltas in matrix order."""
    fixtures = [
        _result(recall=0.30, precision=1.0),  # baseline
        _result(recall=0.50, precision=1.0),  # analyzer-only
        _result(recall=0.60, precision=1.0),  # no-retrieval
        _result(recall=0.80, precision=1.0),  # full
    ]
    fake_run_eval = AsyncMock(side_effect=fixtures)
    monkeypatch.setattr("eval.ablation.run_eval", fake_run_eval)

    samples_dir = tmp_path / "samples"
    samples_dir.mkdir()
    results_dir = tmp_path / "results"

    ablation = await run_ablation(
        samples_dir=samples_dir, results_dir=results_dir
    )

    # Each row is one run_eval call, mode kwarg passed positionally
    # via kwargs in run_eval's signature.
    assert fake_run_eval.await_count == 4
    invoked_modes = [
        call.kwargs.get("mode") for call in fake_run_eval.await_args_list
    ]
    assert tuple(invoked_modes) == ABLATION_ROW_ORDER

    # AblationResult shape: 4 rows + 3 deltas, in the same order.
    assert [r.mode for r in ablation.rows] == list(ABLATION_ROW_ORDER)
    assert len(ablation.deltas) == 3

    # JSON file landed.
    out_files = list(results_dir.glob("ablation-*.json"))
    assert len(out_files) == 1
    payload = json.loads(out_files[0].read_text(encoding="utf-8"))
    assert len(payload["rows"]) == 4
    assert len(payload["deltas"]) == 3
    # Sanity: the recall ordering is preserved through the JSON.
    recalls = [r["result"]["summary"]["recall_at_class"] for r in payload["rows"]]
    assert recalls == [0.30, 0.50, 0.60, 0.80]
