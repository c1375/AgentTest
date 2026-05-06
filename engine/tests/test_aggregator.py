"""Unit tests for the aggregator (`aggregator/emit.py`)."""

from __future__ import annotations

from agenttest.aggregator.emit import aggregate
from agenttest.contracts import GeneratedTest, ValidatedTest


def _v(method_source: str, risk_id: str = "LLM01_Prompt_Injection") -> ValidatedTest:
    return ValidatedTest(
        test=GeneratedTest(
            risk_id=risk_id,
            target_lines=(10, 20),
            test_method_source=method_source,
            assertion_rationale="rationale",
        ),
        compiled_class_bytes=b"",
        runs_clean_on_clean_input=True,
    )


_METHOD_A = """\
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

@Test
void rejectsBreakoutA() {
    assertThat("safe").doesNotContain("evil");
}
"""

_METHOD_B = """\
import static org.assertj.core.api.Assertions.assertThat;
import java.util.Map;

@Test
void rejectsBreakoutB() {
    assertThat(Map.of()).isEmpty();
}
"""


def test_aggregate_merges_methods_and_dedups_imports() -> None:
    emission = aggregate(
        [_v(_METHOD_A), _v(_METHOD_B)],
        target_class_name="RestaurantPromptAssembler",
        target_package="com.example.spring",
        output_path="/tmp/out.java",
    )

    src = emission.java_source

    # Class name + package
    assert "package com.example.spring;" in src
    assert "class RestaurantPromptAssemblerAgentGenTest {" in src

    # Both methods present
    assert "rejectsBreakoutA" in src
    assert "rejectsBreakoutB" in src

    # Imports deduplicated: each line appears exactly once.
    assert src.count("import org.junit.jupiter.api.Test;") == 1
    assert src.count("import static org.assertj.core.api.Assertions.assertThat;") == 1
    assert src.count("import java.util.Map;") == 1

    # Header / advisory note
    assert "OWASP risks covered" in src
    assert "LLM01_Prompt_Injection" in src
    assert "advisory" in src.lower()

    # The original `import` lines should NOT appear inside the method
    # bodies — they got hoisted to the file's import block.
    method_region = src.split("class RestaurantPromptAssemblerAgentGenTest {", 1)[1]
    assert "import " not in method_region


def test_aggregate_collapses_repeated_risk_ids_in_header() -> None:
    emission = aggregate(
        [_v(_METHOD_A), _v(_METHOD_B)],  # both LLM01
        target_class_name="Foo",
        target_package="com.example",
        output_path="/tmp/out.java",
    )
    # `risks_covered` is the de-duplicated, ordered list.
    assert emission.risks_covered == ["LLM01_Prompt_Injection"]


def test_aggregate_empty_validated_emits_explanatory_class() -> None:
    emission = aggregate(
        [],
        target_class_name="Foo",
        target_package="com.example",
        output_path="/tmp/out.java",
    )

    assert emission.risks_covered == []
    src = emission.java_source
    assert "class FooAgentGenTest {" in src
    assert "no tests survived" in src.lower()
    # No method bodies.
    assert "@Test" not in src


def test_aggregate_threads_refused_sites_through() -> None:
    from agenttest.contracts import RefusedSite, RiskSite

    site = RiskSite(
        file_path="Foo.java",
        line_start=1,
        line_end=2,
        site_kind="prompt_assembly",
        method_name="m",
        candidate_risks=["LLM01_Prompt_Injection"],
        snippet="",
    )
    refused = RefusedSite(
        site=site,
        reason="model refused",
        drop_category="model_refused",
    )
    emission = aggregate(
        [],
        target_class_name="Foo",
        target_package="com.example",
        output_path="/tmp/out.java",
        refused_sites=[refused],
    )
    assert emission.refused_sites == [refused]


def test_aggregate_no_package_emits_no_package_line() -> None:
    emission = aggregate(
        [_v(_METHOD_A)],
        target_class_name="Foo",
        target_package="",
        output_path="/tmp/out.java",
    )
    assert "package " not in emission.java_source
