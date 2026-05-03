"""Unit tests for the S1 analyzer rule (prompt_assembly -> LLM01)."""

import asyncio
from pathlib import Path

from agenttest.analyzer.identify import AnalyzerInput, identify


FIXTURES = Path(__file__).parent / "fixtures"


CLEAN_NO_PROMPT_JAVA = """\
package com.example;

public class CleanService {

    public String greet(String name) {
        return "hello, " + name;
    }
}
"""


def test_identify_detects_prompt_template_assembler() -> None:
    fixture_path = FIXTURES / "RestaurantPromptAssembler.java"
    java_source = fixture_path.read_text(encoding="utf-8")

    sites = asyncio.run(
        identify(AnalyzerInput(
            java_source=java_source,
            file_path=str(fixture_path),
        ))
    )

    assert len(sites) >= 1
    site = sites[0]
    assert site.site_kind == "prompt_assembly"
    assert "LLM01_Prompt_Injection" in site.candidate_risks
    assert site.method_name == "assemble"
    assert site.file_path == str(fixture_path)
    assert site.line_start <= site.line_end
    assert "PromptTemplate" in site.snippet


def test_identify_returns_empty_when_no_prompt_template() -> None:
    sites = asyncio.run(
        identify(AnalyzerInput(
            java_source=CLEAN_NO_PROMPT_JAVA,
            file_path="CleanService.java",
        ))
    )

    assert sites == []
