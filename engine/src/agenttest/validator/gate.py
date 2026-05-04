"""Validator gate: parse-check then run-on-clean.

Order matters: parse-check is cheap (<10ms) and rejects obvious
garbage; run-on-clean is slow (full JVM compile + JUnit launch) and
verifies the test actually compiles, runs, and passes on the un-
mutated target. A surviving test maps to a `ValidatedTest` with
`runs_clean_on_clean_input=True`. A dropped test maps to `None` and
the caller logs the reason.

`compiled_class_bytes` is set to empty bytes in S2 — the runner-helper
doesn't return them and no downstream stage in S2 needs them. TODO(S3):
populate when the aggregator's classpath check needs them.
"""

from __future__ import annotations

import logging
from pathlib import Path

from agenttest.contracts import GeneratedTest, ValidatedTest
from agenttest.validator.parse import parse_check
from agenttest.validator.run import run_on_clean, wrap_test_method

logger = logging.getLogger(__name__)


def validate_gate(
    generated: GeneratedTest,
    *,
    target_class_path: Path,
    target_class_name: str,
    target_package: str,
) -> ValidatedTest | None:
    """Run the parse and run-on-clean gates; return None to drop."""
    if generated.refused:
        # Caller should have filtered already, but be defensive.
        logger.info(
            "[validator] skipping refused generation for %s",
            generated.risk_id,
        )
        return None

    if not parse_check(generated.test_method_source):
        logger.info(
            "[validator] dropped %s: parse-check failed",
            generated.risk_id,
        )
        return None

    test_class_source, test_class_fqn = wrap_test_method(
        generated.test_method_source,
        target_class_name=target_class_name,
        target_package=target_package,
    )

    result = run_on_clean(
        target_class_path=target_class_path,
        test_class_source=test_class_source,
        test_class_fqn=test_class_fqn,
    )
    if result.outcome != "PASS":
        logger.info(
            "[validator] dropped %s: run-on-clean returned %s\n%s",
            generated.risk_id,
            result.outcome,
            result.details,
        )
        # Dump the wrapped test source at DEBUG so prompt-iteration
        # cycles can see exactly what Sonnet emitted, without spamming
        # normal runs.
        logger.debug(
            "[validator] dropped test source for %s:\n%s",
            generated.risk_id,
            test_class_source,
        )
        return None

    return ValidatedTest(
        test=generated,
        compiled_class_bytes=b"",
        runs_clean_on_clean_input=True,
    )
