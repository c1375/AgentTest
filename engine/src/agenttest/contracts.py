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
    "log_handler",          # logs user-attributable input via JUL/SLF4J (LLM02)
    "mcp_endpoint",         # MCP server tool registration / handler
    "tenant_boundary",      # privileged op that takes tenantId
    "retry_config",         # Resilience4j or similar retry/CB config
]


# Why a single category enum: S4 ablation needs to compute
# "ship-bad-tests rate" per pipeline mode, defined as the % of pairs
# where the mode would have shipped a test that fails on clean code
# absent the validator gate. Only `compile_fail` and `clean_fail` count
# toward that metric — other drop reasons (model refused, no catalog
# entry, API error, parse-check failure) didn't produce test code that
# would have shipped. The category lets eval/results.py compute the
# metric without inspecting free-text reason strings.
DropCategory = Literal[
    "no_catalog_entry",     # pre-LLM: site flagged a risk we have no OWASP entry for
    "api_error",            # LLM call raised AnthropicError
    "model_refused",        # generator returned `refused: true`
    "parse_check_failed",   # validator: javalang couldn't parse the method body
    "compile_fail",         # validator: javac failed on the wrapped class
    "clean_fail",           # validator: test ran but failed/errored on the clean target
    "runner_error",         # validator: runner-helper returned ERROR (timeout, missing toolchain)
    "other",                # catch-all
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
class BaselineEmission:
    """Output of `baseline.synthesize.synthesize_baseline`.

    The single-prompt comparison's emission. Mirrors `TestClassEmission`
    in shape — both end up running through the same eval gate (compile
    + run-on-clean + run-on-buggy) — but baseline carries no
    risks_covered or refused_sites because it doesn't track per-risk
    inside the pipeline.

    `parseable` flags whether `java_source` parses as Java. False
    means the model returned something that isn't recoverable as a
    test class (e.g., refused, returned only prose, or emitted broken
    Java); the eval runner treats these as a separate audit category
    so they don't pollute recall/precision math.
    """
    target_class_name: str
    java_source: str         # extracted from a markdown fence if present, else raw
    parseable: bool          # True if javalang.parse succeeded on java_source


@dataclass(frozen=True)
class OwaspEntry:
    risk_id: OwaspRiskId
    title: str
    description: str
    invariant_to_assert: str   # machine-readable contract — load-bearing for the generator
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
class RefusedSite:
    """One refusal in the pipeline — site, human-readable reason, machine-
    readable category. Replaced the (RiskSite, str) tuple in S4 to support
    the ship-bad-tests-rate metric."""
    site: RiskSite
    reason: str
    drop_category: DropCategory


@dataclass(frozen=True)
class TestClassEmission:
    """Output of aggregator; final pipeline output."""
    target_class_name: str
    output_path: str
    java_source: str
    risks_covered: list[OwaspRiskId]
    refused_sites: list[RefusedSite]
