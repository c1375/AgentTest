"""Unit tests for analyzer rules.

S1 covers prompt_assembly -> LLM01. S3 adds tool_handler -> LLM06 and
log_handler -> LLM02. Positive tests use the real eval samples (so
analyzer agrees with sample reality); negative tests use inline
synthetic Java for each "this should NOT match" boundary case.
"""

import asyncio
from pathlib import Path

import pytest

from agenttest.analyzer.identify import AnalyzerInput, identify

FIXTURES = Path(__file__).parent / "fixtures"
ENGINE_ROOT = Path(__file__).resolve().parent.parent
EVAL_SAMPLES = ENGINE_ROOT / "eval" / "samples" / "spring_ai"


def _run_identify(java_source: str, file_path: str) -> list:
    return asyncio.run(
        identify(AnalyzerInput(java_source=java_source, file_path=file_path))
    )


CLEAN_NO_PROMPT_JAVA = """\
package com.example;

public class CleanService {

    public String greet(String name) {
        return "hello, " + name;
    }
}
"""


# ---------------------------------------------------------------------------
# S1: prompt_assembly -> LLM01
# ---------------------------------------------------------------------------


def test_identify_detects_prompt_template_assembler() -> None:
    fixture_path = FIXTURES / "RestaurantPromptAssembler.java"
    java_source = fixture_path.read_text(encoding="utf-8")

    sites = _run_identify(java_source, str(fixture_path))

    assert len(sites) >= 1
    site = sites[0]
    assert site.site_kind == "prompt_assembly"
    assert "LLM01_Prompt_Injection" in site.candidate_risks
    assert site.method_name == "assemble"
    assert site.file_path == str(fixture_path)
    assert site.line_start <= site.line_end
    assert "PromptTemplate" in site.snippet


def test_identify_returns_empty_when_no_prompt_template() -> None:
    sites = _run_identify(CLEAN_NO_PROMPT_JAVA, "CleanService.java")
    assert sites == []


# ---------------------------------------------------------------------------
# S3 Step 1: tool_handler -> LLM06
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sample_filename, expected_method",
    [
        ("MenuMcpServer.java", "searchMenu"),
        ("WeatherTool.java", "currentWeather"),
    ],
)
def test_identify_detects_tool_handler_with_description(
    sample_filename: str, expected_method: str
) -> None:
    """Real eval samples must surface their @Tool method as a tool_handler site."""
    sample_path = EVAL_SAMPLES / sample_filename
    sites = _run_identify(sample_path.read_text(encoding="utf-8"), str(sample_path))

    tool_sites = [s for s in sites if s.site_kind == "tool_handler"]
    assert len(tool_sites) == 1, f"expected exactly one tool_handler site, got {tool_sites}"
    site = tool_sites[0]
    assert site.method_name == expected_method
    assert "LLM06_Excessive_Agency" in site.candidate_risks


_TOOL_EMPTY_DESC_JAVA = """\
package com.example;
import org.springframework.ai.tool.annotation.Tool;
public class T {
    @Tool(description = "")
    public String run() { return null; }
}
"""

_TOOL_NO_DESC_JAVA = """\
package com.example;
import org.springframework.ai.tool.annotation.Tool;
public class T {
    @Tool
    public String run() { return null; }

    @Tool(name = "only-name")
    public String run2() { return null; }
}
"""

_NO_TOOL_JAVA = """\
package com.example;
public class T {
    @Override
    public String toString() { return "x"; }
}
"""


@pytest.mark.parametrize(
    "java_source, label",
    [
        (_TOOL_EMPTY_DESC_JAVA, "empty-description"),
        (_TOOL_NO_DESC_JAVA, "no-description-attribute"),
        (_NO_TOOL_JAVA, "no-Tool-annotation-at-all"),
    ],
)
def test_identify_skips_tool_without_nonempty_description(
    java_source: str, label: str
) -> None:
    sites = _run_identify(java_source, f"T-{label}.java")
    assert not any(s.site_kind == "tool_handler" for s in sites), (
        f"unexpected tool_handler site for {label}: {sites}"
    )


# ---------------------------------------------------------------------------
# S3 Step 2: log_handler -> LLM02
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sample_filename, expected_method",
    [
        ("AgentLogger.java", "logRequest"),
        ("RequestAuditTrail.java", "recordInvocation"),
    ],
)
def test_identify_detects_log_handler_with_param_in_log_call(
    sample_filename: str, expected_method: str
) -> None:
    """Real LLM02 samples must surface their log-emitting method as a log_handler site."""
    sample_path = EVAL_SAMPLES / sample_filename
    sites = _run_identify(sample_path.read_text(encoding="utf-8"), str(sample_path))

    log_sites = [s for s in sites if s.site_kind == "log_handler"]
    assert len(log_sites) == 1, f"expected exactly one log_handler site, got {log_sites}"
    site = log_sites[0]
    assert site.method_name == expected_method
    assert "LLM02_Sensitive_Information_Disclosure" in site.candidate_risks


_LOG_PRIMITIVE_PARAMS_ONLY_JAVA = """\
package com.example;
import java.util.logging.Logger;
public class L {
    private static final Logger logger = Logger.getLogger(L.class.getName());
    public void run(int count, boolean enabled) {
        logger.info("count=" + count + " enabled=" + enabled);
    }
}
"""

_LOG_NO_PARAM_REFERENCE_JAVA = """\
package com.example;
import java.util.logging.Logger;
public class L {
    private static final Logger logger = Logger.getLogger(L.class.getName());
    public void run(String userInput) {
        logger.info("static text only — userInput is unused in the log");
    }
}
"""

_LOG_NO_LOGGER_FIELD_JAVA = """\
package com.example;
public class L {
    public void run(String userInput) {
        System.out.println(userInput);  // not a Logger field
    }
}
"""


@pytest.mark.parametrize(
    "java_source, label",
    [
        (_LOG_PRIMITIVE_PARAMS_ONLY_JAVA, "primitives-only"),
        (_LOG_NO_PARAM_REFERENCE_JAVA, "no-param-reference"),
        (_LOG_NO_LOGGER_FIELD_JAVA, "no-logger-field"),
    ],
)
def test_identify_skips_log_handler_when_heuristic_fails(
    java_source: str, label: str
) -> None:
    sites = _run_identify(java_source, f"L-{label}.java")
    assert not any(s.site_kind == "log_handler" for s in sites), (
        f"unexpected log_handler site for {label}: {sites}"
    )


# ---------------------------------------------------------------------------
# Cross-rule sanity: a sample with neither risk emits no S3 site
# ---------------------------------------------------------------------------


def test_identify_real_llm01_sample_emits_no_s3_sites() -> None:
    """RestaurantPromptAssembler has no @Tool and no Logger field — only
    its prompt_assembly site should surface, no tool_handler/log_handler.
    """
    sample_path = EVAL_SAMPLES / "RestaurantPromptAssembler.java"
    sites = _run_identify(sample_path.read_text(encoding="utf-8"), str(sample_path))

    assert any(s.site_kind == "prompt_assembly" for s in sites)
    assert not any(s.site_kind in {"tool_handler", "log_handler"} for s in sites)
