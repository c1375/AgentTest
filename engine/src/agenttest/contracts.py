"""Stage contracts shared across the AgentTest pipeline.

These dataclasses are the typed, frozen handoffs between stages
(analyzer -> retriever -> generator -> validator -> aggregator). They are
defined verbatim in `docs/plan/architecture.md` and no stage may invent
its own RiskSite / Grounding / GeneratedTest shape — import from here.
"""

from dataclasses import dataclass
from typing import Literal

OwaspRiskId = str  # e.g., "LLM01_Prompt_Injection", "Agentic_Multi_Tenant"

SiteKind = Literal[
    "prompt_assembly",      # builds a PromptTemplate from user input
    "tool_handler",         # @Tool method or LangChain4j tool implementation
    "mcp_endpoint",         # MCP server tool registration / handler
    "tenant_boundary",      # privileged op that takes tenantId
    "retry_config",         # Resilience4j or similar retry/CB config
]


@dataclass(frozen=True)
class RiskSite:
    """Output of analyzer; input to retriever."""
    file_path: str
    line_start: int
    line_end: int
    site_kind: SiteKind
    method_name: str
    candidate_risks: list[OwaspRiskId]   # ordered by analyzer's confidence
    snippet: str                          # raw source for the site


@dataclass(frozen=True)
class OwaspEntry:
    risk_id: OwaspRiskId
    title: str
    description: str
    exemplar_java: str
    exemplar_test: str


@dataclass(frozen=True)
class PatternExample:
    pattern_id: str          # e.g., "spring_ai/prompt_template_basic"
    description: str
    java_source: str
    similarity: float        # cosine, 0-1


@dataclass(frozen=True)
class Grounding:
    """Output of retriever; input to generator. One per (site, candidate_risk) pair."""
    site: RiskSite
    risk_id: OwaspRiskId
    owasp_entry: OwaspEntry
    pattern_examples: list[PatternExample]   # top-3, ordered


@dataclass(frozen=True)
class GeneratedTest:
    """Output of generator. Mirrors the JSON schema the LLM returns."""
    risk_id: OwaspRiskId
    target_lines: tuple[int, int]
    test_method_source: str
    assertion_rationale: str
    refused: bool = False
    refusal_reason: str | None = None


@dataclass(frozen=True)
class ValidatedTest:
    """Output of validator. Surviving tests only."""
    test: GeneratedTest
    compiled_class_bytes: bytes      # for the aggregator's classpath check
    runs_clean_on_clean_input: bool  # always True after validator gate


@dataclass(frozen=True)
class TestClassEmission:
    """Output of aggregator; final pipeline output."""
    target_class_name: str
    output_path: str
    java_source: str
    risks_covered: list[OwaspRiskId]
    refused_sites: list[tuple[RiskSite, str]]  # (site, reason) for refusals
