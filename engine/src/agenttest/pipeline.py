"""Shared async pipeline driving analyzer -> retriever -> generator -> ...

S1 only runs the analyzer stage. Retriever / generator / validator /
aggregator are stubbed — `TestClassEmission.java_source` is a placeholder
and every detected site lands in `refused_sites` with a "not yet
implemented" reason. S2 fills in the real stages.

Progress is logged via stdlib `logging` for now. S3 replaces these log
calls with an async event stream consumed by both the CLI and the
FastAPI SSE route.
"""

import logging
from pathlib import Path

from agenttest.analyzer.identify import AnalyzerInput, identify
from agenttest.contracts import RiskSite, TestClassEmission

logger = logging.getLogger(__name__)

_GENERATOR_REFUSAL_REASON = "generator stage not yet implemented"
_PLACEHOLDER_JAVA = "// AgentTest S1 stub — generator stage not yet implemented"


def _output_path_for(input_path: Path, target_class_name: str) -> str:
    return str(input_path.parent / f"{target_class_name}SecurityGenTest.java")


async def run(input_path: str | Path) -> TestClassEmission:
    """Run the S1 pipeline and return a placeholder `TestClassEmission`."""
    path = Path(input_path)
    java_source = path.read_text(encoding="utf-8")

    logger.info("[pipeline] reading %s", path)

    analyzer_input = AnalyzerInput(java_source=java_source, file_path=str(path))
    sites: list[RiskSite] = await identify(analyzer_input)
    logger.info("[analyzer] found %d risk site(s)", len(sites))

    target_class_name = path.stem
    output_path = _output_path_for(path, target_class_name)

    refused_sites: list[tuple[RiskSite, str]] = [
        (site, _GENERATOR_REFUSAL_REASON) for site in sites
    ]

    return TestClassEmission(
        target_class_name=target_class_name,
        output_path=output_path,
        java_source=_PLACEHOLDER_JAVA,
        risks_covered=[],
        refused_sites=refused_sites,
    )
