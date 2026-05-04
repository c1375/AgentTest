"""Shared async pipeline driving analyzer -> generator -> validator -> aggregator.

S2 wires the full pipeline end-to-end for LLM01:

    analyze (S1, in-process)
      -> for each (site, candidate_risk):
           build Grounding from OWASP catalog (no retrieval in S2 —
                                               see sprint-2.md
                                               "Locked decision 4")
           generate (LLM call via test_synthesizer)
           validate (parse-check + run-on-clean against the runner-helper)
      -> aggregate surviving methods into one Java class

Refused sites (no catalog entry, model refused, JSON parse failure
after retry, or validator dropped) are threaded into
`TestClassEmission.refused_sites` so the CLI can report them.

Progress is logged via stdlib `logging`. S3 replaces these log calls
with an async event stream consumed by both the CLI and the FastAPI
SSE route.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from anthropic import AnthropicError

from agenttest.agents.factory import AgentClientFactory
from agenttest.agents.role import AgentRole
from agenttest.aggregator.emit import aggregate
from agenttest.analyzer.identify import AnalyzerInput, identify
from agenttest.config import settings
from agenttest.contracts import (
    Grounding,
    RiskSite,
    TestClassEmission,
    ValidatedTest,
)
from agenttest.generator.synthesize import synthesize
from agenttest.retrieval.owasp import load_owasp
from agenttest.validator.gate import validate_gate

logger = logging.getLogger(__name__)


_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)


def _output_path_for(input_path: Path, target_class_name: str) -> str:
    return str(input_path.parent / f"{target_class_name}SecurityGenTest.java")


def _infer_package(java_source: str) -> str:
    """Return the `package x.y.z` declaration's value, or '' if absent."""
    m = _PACKAGE_RE.search(java_source)
    return m.group(1) if m else ""


async def run(input_path: str | Path) -> TestClassEmission:
    """Run the full S2 pipeline on `input_path` and return the emission."""
    path = Path(input_path)
    java_source = path.read_text(encoding="utf-8")
    logger.info("[pipeline] reading %s", path)

    analyzer_input = AnalyzerInput(java_source=java_source, file_path=str(path))
    sites: list[RiskSite] = await identify(analyzer_input)
    logger.info("[analyzer] found %d risk site(s)", len(sites))

    target_class_name = path.stem
    target_package = _infer_package(java_source)
    target_class_fqn = (
        f"{target_package}.{target_class_name}" if target_package else target_class_name
    )
    output_path = _output_path_for(path, target_class_name)

    # Empty short-circuit: if no sites, emit a placeholder header-only
    # class with empty `risks_covered`. This keeps the CLI happy on
    # non-AI Java files (the user hasn't broken anything; we just have
    # nothing to test).
    if not sites:
        logger.info("[pipeline] no risk sites — emitting empty test class")
        return aggregate(
            [],
            target_class_name=target_class_name,
            target_package=target_package,
            refused_sites=[],
            output_path=output_path,
        )

    factory = AgentClientFactory.from_settings(settings)
    try:
        client = factory.get(AgentRole.TEST_SYNTHESIZER)
        owasp_catalog = load_owasp(settings.configs_dir / "owasp.yaml")
        logger.info("[pipeline] loaded %d OWASP catalog entries", len(owasp_catalog))

        validated: list[ValidatedTest] = []
        refused: list[tuple[RiskSite, str]] = []

        for site in sites:
            for risk_id in site.candidate_risks:
                if risk_id not in owasp_catalog:
                    logger.info(
                        "[pipeline] no catalog entry for %s — skipping site %s",
                        risk_id,
                        site.method_name,
                    )
                    refused.append((site, f"no catalog entry for {risk_id}"))
                    continue

                grounding = Grounding(
                    site=site,
                    risk_id=risk_id,
                    owasp_entry=owasp_catalog[risk_id],
                    pattern_examples=[],  # S2: empty per sprint-2.md "Locked decision 4"
                )
                logger.info(
                    "[generator] synthesizing for %s @ %s:%d-%d",
                    risk_id,
                    site.method_name,
                    site.line_start,
                    site.line_end,
                )

                try:
                    generated = await synthesize(
                        grounding,
                        client,
                        owasp_catalog,
                        target_class_fqn=target_class_fqn,
                    )
                except AnthropicError as exc:
                    # API/network/auth failures fail this site only; the
                    # next site might succeed (e.g., transient 429). Other
                    # exception types (TypeError, AttributeError) are
                    # programmer bugs and propagate up to the CLI.
                    logger.info(
                        "[generator] Anthropic API error for %s @ %s: %s: %s",
                        risk_id,
                        site.method_name,
                        type(exc).__name__,
                        exc,
                    )
                    refused.append((site, f"{type(exc).__name__}: {exc}"))
                    continue

                if generated.refused:
                    refused.append((site, generated.refusal_reason or "model refused"))
                    continue

                # validate_gate is sync (subprocess to JVM); wrap so the
                # JVM compile+run doesn't stall the event loop. S3 will
                # convert the subprocess itself to asyncio.create_subprocess_exec
                # per engine/CLAUDE.md.
                v = await asyncio.to_thread(
                    validate_gate,
                    generated,
                    target_class_path=path,
                    target_class_name=target_class_name,
                    target_package=target_package,
                )
                if v is None:
                    refused.append((site, "validator dropped"))
                    continue
                validated.append(v)
                logger.info(
                    "[validator] kept test for %s @ %s",
                    risk_id,
                    site.method_name,
                )
    finally:
        await factory.aclose()

    logger.info(
        "[pipeline] %d test(s) survived validation; %d site(s) refused",
        len(validated),
        len(refused),
    )

    return aggregate(
        validated,
        target_class_name=target_class_name,
        target_package=target_package,
        refused_sites=refused,
        output_path=output_path,
    )
