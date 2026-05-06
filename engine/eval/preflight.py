"""Sample × injection round-trip preflight check.

For every sample under `eval/samples/` and every injection listed in
its `meta.yaml#applicable_injections`, run the injection's `apply()`
on the clean Java source and assert the output is **non-trivially
different** from the input. A no-op diff means the injection's
regex / AST pattern didn't actually match — which silently produces
`pipeline_error` rows in the eval, polluting the headline numbers
without any obvious symptom.

This module is a ship-blocker per `docs/plan/sprint-4.md` Step 1.5:
it gets run as a pytest in CI (`tests/test_eval_preflight.py`) AND
as a sanity-check before any real-LLM ablation run.

Run from `engine/`:

    py -3.13 eval/preflight.py

Exit code: 0 if all pairs pass, 1 if any finding.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from eval.injections import INJECTIONS_BY_NAME  # noqa: E402

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreflightFinding:
    """One sample × injection pair that failed preflight.

    `issue` is the machine-readable category; `details` carries the
    human-readable specifics. The categories are stable so the pytest
    harness can assert on them without text-matching `details`.
    """
    sample_id: str
    injection_name: str
    issue: str  # one of: no_op, not_applicable, unknown_injection, missing_sample_file, malformed_meta, unexpected_error
    details: str


def _load_meta(meta_path: Path) -> dict:
    """Load and shallow-validate a sample's meta.yaml.

    Mirrors the loader in eval/runner.py but tolerates missing fields
    so we can still produce a structured finding rather than crash.
    """
    raw = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{meta_path} did not parse to a mapping")
    return raw


def _resolve_clean_java_path(meta_path: Path, target_class: str) -> Path:
    return meta_path.parent / f"{target_class}.java"


def check_pair(
    meta_path: Path,
    sample_id: str,
    target_class: str,
    injection_name: str,
) -> PreflightFinding | None:
    """Round-trip one (sample, injection) pair. Return None on success."""
    injection_cls = INJECTIONS_BY_NAME.get(injection_name)
    if injection_cls is None:
        return PreflightFinding(
            sample_id=sample_id,
            injection_name=injection_name,
            issue="unknown_injection",
            details=(
                f"meta.yaml lists injection {injection_name!r} but it is "
                f"not registered in INJECTIONS_BY_NAME. Known: "
                f"{sorted(INJECTIONS_BY_NAME)}"
            ),
        )

    java_path = _resolve_clean_java_path(meta_path, target_class)
    if not java_path.exists():
        return PreflightFinding(
            sample_id=sample_id,
            injection_name=injection_name,
            issue="missing_sample_file",
            details=f"expected {java_path.name} next to {meta_path.name}, not found",
        )

    clean_source = java_path.read_text(encoding="utf-8")
    try:
        buggy_source = injection_cls().apply(clean_source)
    except ValueError as exc:
        # Per Injection.apply contract: ValueError means "not applicable
        # to this source." That's a meta.yaml correctness issue — the
        # sample's `applicable_injections` lied.
        return PreflightFinding(
            sample_id=sample_id,
            injection_name=injection_name,
            issue="not_applicable",
            details=f"{type(exc).__name__}: {exc}",
        )
    except Exception as exc:  # noqa: BLE001
        return PreflightFinding(
            sample_id=sample_id,
            injection_name=injection_name,
            issue="unexpected_error",
            details=f"{type(exc).__name__}: {exc}",
        )

    # Non-trivial change check: stripped sources must differ. Whitespace-
    # only diffs are excluded because Java compilers ignore them and the
    # eval would silently see "no change" once the runner-helper formats.
    if clean_source.strip() == buggy_source.strip():
        return PreflightFinding(
            sample_id=sample_id,
            injection_name=injection_name,
            issue="no_op",
            details=(
                "injection.apply() returned source byte-equal (after strip) "
                "to the clean input. The regex / AST pattern likely did not "
                "match — fix the injection's pattern, the sample's source, "
                "or remove this injection from applicable_injections."
            ),
        )

    return None


def preflight_check(
    samples_dir: Path = Path("eval/samples"),
) -> list[PreflightFinding]:
    """Round-trip every (sample, applicable_injection) pair.

    Returns an empty list when all pairs pass. Each entry in the
    returned list is a structured finding the caller (pytest or CLI)
    can render however it likes.
    """
    samples_dir = samples_dir.resolve()
    findings: list[PreflightFinding] = []

    meta_paths = sorted(samples_dir.glob("**/*.meta.yaml"))
    for meta_path in meta_paths:
        try:
            meta = _load_meta(meta_path)
        except (yaml.YAMLError, ValueError) as exc:
            findings.append(PreflightFinding(
                sample_id=str(meta_path.relative_to(samples_dir)),
                injection_name="(meta load)",
                issue="malformed_meta",
                details=f"{type(exc).__name__}: {exc}",
            ))
            continue

        sample_id = meta.get("sample_id", str(meta_path.relative_to(samples_dir)))
        target_class = meta.get("target_class")
        injections = meta.get("applicable_injections") or []

        if target_class is None:
            findings.append(PreflightFinding(
                sample_id=sample_id,
                injection_name="(meta load)",
                issue="malformed_meta",
                details="missing required field: target_class",
            ))
            continue

        for injection_name in injections:
            finding = check_pair(
                meta_path=meta_path,
                sample_id=sample_id,
                target_class=target_class,
                injection_name=injection_name,
            )
            if finding is not None:
                findings.append(finding)

    return findings


def main() -> int:
    samples_dir = ENGINE_ROOT / "eval" / "samples"
    findings = preflight_check(samples_dir=samples_dir)

    if not findings:
        # Count for the OK message; a silent OK is harder to debug if a
        # CI script accidentally runs preflight on an empty samples dir.
        meta_count = len(sorted(samples_dir.glob("**/*.meta.yaml")))
        print(
            f"Preflight OK: all (sample × applicable_injection) pairs "
            f"in {meta_count} meta.yaml file(s) produce non-trivial diffs."
        )
        return 0

    for f in findings:
        print(f"  {f.sample_id} / {f.injection_name} [{f.issue}]: {f.details}")
    print()
    print(f"Preflight FAILED: {len(findings)} issue(s) across {samples_dir}")
    return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
