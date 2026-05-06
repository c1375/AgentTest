"""Tests for eval/preflight.py.

Two flavors:

1. Unit tests on `check_pair` with synthetic injections + a tmp samples
   dir, covering each PreflightFinding.issue category.

2. Real-tree assertion: `preflight_check` over the actual
   `engine/eval/samples/` tree must return an empty findings list.
   This is the ship-blocker — a no-op injection silently produces
   `pipeline_error` rows in the eval, contaminating the headline
   numbers without an obvious symptom. The assertion failing in CI
   is the early-warning signal we did not have in S3.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from eval.injections import INJECTIONS_BY_NAME  # noqa: E402
from eval.injections.base import Injection  # noqa: E402
from eval.preflight import (  # noqa: E402
    PreflightFinding,
    check_pair,
    preflight_check,
)


# ---------------------------------------------------------------------------
# Synthetic fixtures: a tmp samples dir + opt-in fake injections registered
# into INJECTIONS_BY_NAME for the duration of one test.
# ---------------------------------------------------------------------------


class _NoOpInjection(Injection):
    """Returns input unchanged — the silent failure mode preflight catches."""
    name = "_noop_test_injection"

    def apply(self, java_source: str) -> str:
        return java_source


class _NotApplicableInjection(Injection):
    """Raises ValueError per the Injection.apply contract."""
    name = "_notapplicable_test_injection"

    def apply(self, java_source: str) -> str:
        raise ValueError("pattern not found in source")


class _BoomInjection(Injection):
    """Raises an unexpected (non-ValueError) exception."""
    name = "_boom_test_injection"

    def apply(self, java_source: str) -> str:
        raise RuntimeError("kaboom")


class _RealChangeInjection(Injection):
    """Returns a non-trivially modified source — the happy path."""
    name = "_realchange_test_injection"

    def apply(self, java_source: str) -> str:
        return java_source + "\n// injected\n"


@pytest.fixture
def fake_injections(monkeypatch: pytest.MonkeyPatch) -> None:
    """Register the synthetic injections for the test's duration only.

    monkeypatch.setitem auto-reverses on test teardown so the global
    INJECTIONS_BY_NAME stays clean across the suite.
    """
    for cls in (
        _NoOpInjection,
        _NotApplicableInjection,
        _BoomInjection,
        _RealChangeInjection,
    ):
        monkeypatch.setitem(INJECTIONS_BY_NAME, cls.name, cls)


def _write_sample(
    samples_root: Path,
    *,
    sample_id: str,
    target_class: str,
    target_package: str = "com.example.fake",
    applicable_injections: list[str] | None = None,
    java_body: str | None = None,
    omit_target_class: bool = False,
    omit_java_file: bool = False,
) -> Path:
    """Write a minimal sample dir under `samples_root` and return the
    meta.yaml path."""
    sample_dir = samples_root / sample_id.replace("/", "_")
    sample_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "sample_id": sample_id,
        "target_package": target_package,
        "applicable_injections": applicable_injections or [],
    }
    if not omit_target_class:
        meta["target_class"] = target_class

    import yaml as _yaml
    meta_path = sample_dir / f"{target_class.lower()}.meta.yaml"
    meta_path.write_text(_yaml.safe_dump(meta), encoding="utf-8")

    if not omit_java_file:
        java_text = java_body or f"package {target_package};\n\nclass {target_class} {{}}\n"
        (sample_dir / f"{target_class}.java").write_text(java_text, encoding="utf-8")

    return meta_path


# ---------------------------------------------------------------------------
# check_pair (unit)
# ---------------------------------------------------------------------------


class TestCheckPair:
    def test_real_change_returns_none(
        self, tmp_path: Path, fake_injections: None
    ) -> None:
        meta_path = _write_sample(
            tmp_path, sample_id="t/realchange",
            target_class="Foo",
            applicable_injections=[_RealChangeInjection.name],
        )
        finding = check_pair(
            meta_path=meta_path,
            sample_id="t/realchange",
            target_class="Foo",
            injection_name=_RealChangeInjection.name,
        )
        assert finding is None

    def test_no_op_injection_flagged(
        self, tmp_path: Path, fake_injections: None
    ) -> None:
        meta_path = _write_sample(
            tmp_path, sample_id="t/noop", target_class="Foo",
        )
        finding = check_pair(
            meta_path=meta_path,
            sample_id="t/noop",
            target_class="Foo",
            injection_name=_NoOpInjection.name,
        )
        assert finding is not None
        assert finding.issue == "no_op"

    def test_not_applicable_flagged(
        self, tmp_path: Path, fake_injections: None
    ) -> None:
        meta_path = _write_sample(
            tmp_path, sample_id="t/na", target_class="Foo",
        )
        finding = check_pair(
            meta_path=meta_path,
            sample_id="t/na",
            target_class="Foo",
            injection_name=_NotApplicableInjection.name,
        )
        assert finding is not None
        assert finding.issue == "not_applicable"
        assert "pattern not found" in finding.details

    def test_unexpected_error_flagged(
        self, tmp_path: Path, fake_injections: None
    ) -> None:
        meta_path = _write_sample(
            tmp_path, sample_id="t/boom", target_class="Foo",
        )
        finding = check_pair(
            meta_path=meta_path,
            sample_id="t/boom",
            target_class="Foo",
            injection_name=_BoomInjection.name,
        )
        assert finding is not None
        assert finding.issue == "unexpected_error"
        assert "RuntimeError" in finding.details

    def test_unknown_injection_flagged(self, tmp_path: Path) -> None:
        meta_path = _write_sample(
            tmp_path, sample_id="t/typo", target_class="Foo",
        )
        finding = check_pair(
            meta_path=meta_path,
            sample_id="t/typo",
            target_class="Foo",
            injection_name="this_injection_does_not_exist",
        )
        assert finding is not None
        assert finding.issue == "unknown_injection"

    def test_missing_sample_file_flagged(
        self, tmp_path: Path, fake_injections: None
    ) -> None:
        meta_path = _write_sample(
            tmp_path, sample_id="t/missing", target_class="Foo",
            omit_java_file=True,
        )
        finding = check_pair(
            meta_path=meta_path,
            sample_id="t/missing",
            target_class="Foo",
            injection_name=_RealChangeInjection.name,
        )
        assert finding is not None
        assert finding.issue == "missing_sample_file"


# ---------------------------------------------------------------------------
# preflight_check (unit, on synthetic samples dir)
# ---------------------------------------------------------------------------


class TestPreflightCheck:
    def test_empty_samples_dir_yields_empty_findings(self, tmp_path: Path) -> None:
        # No meta.yaml files at all → no work to do, no findings.
        findings = preflight_check(samples_dir=tmp_path)
        assert findings == []

    def test_meta_missing_target_class_flagged(self, tmp_path: Path) -> None:
        _write_sample(
            tmp_path, sample_id="t/badmeta", target_class="Foo",
            applicable_injections=[],
            omit_target_class=True,
        )
        findings = preflight_check(samples_dir=tmp_path)
        assert len(findings) == 1
        assert findings[0].issue == "malformed_meta"

    def test_iterates_all_pairs(
        self, tmp_path: Path, fake_injections: None
    ) -> None:
        """One sample listing two injections produces one finding per
        bad injection — we don't bail on the first."""
        _write_sample(
            tmp_path, sample_id="t/multi", target_class="Foo",
            applicable_injections=[
                _NoOpInjection.name,
                _NotApplicableInjection.name,
                _RealChangeInjection.name,  # this one passes
            ],
        )
        findings = preflight_check(samples_dir=tmp_path)
        assert len(findings) == 2
        issues = sorted(f.issue for f in findings)
        assert issues == ["no_op", "not_applicable"]


# ---------------------------------------------------------------------------
# Real-tree assertion (the ship-blocker)
# ---------------------------------------------------------------------------


def test_real_samples_dir_has_no_preflight_findings() -> None:
    """Every (sample, applicable_injection) pair under
    `engine/eval/samples/` must produce a non-trivial diff.

    A finding here means a sample's `applicable_injections` lies — the
    eval will silently produce `pipeline_error` rows rather than
    measuring the risk. This test fails fast before any LLM call burns
    budget on a contaminated sample set.
    """
    samples_dir = ENGINE_ROOT / "eval" / "samples"
    findings = preflight_check(samples_dir=samples_dir)
    assert findings == [], (
        "Preflight findings on real samples dir:\n"
        + "\n".join(
            f"  - {f.sample_id} / {f.injection_name} [{f.issue}]: {f.details}"
            for f in findings
        )
    )
