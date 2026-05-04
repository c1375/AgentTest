"""Unit tests for the generator (`generator/synthesize.py`).

All five cases run with a mocked `AgentClient.complete`. No real
Anthropic call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest

from agenttest.contracts import (
    GeneratedTest,
    Grounding,
    OwaspEntry,
    RiskSite,
)
from agenttest.generator.synthesize import (
    JsonExtractionError,
    extract_json,
    synthesize,
)

# --- fakes -----------------------------------------------------------------


@dataclass
class _FakeContentBlock:
    """Mimics anthropic.types.TextBlock — only the .text attribute is read."""

    text: str


@dataclass
class _FakeMessage:
    """Mimics anthropic.types.Message — only .content[0].text is read."""

    content: list[_FakeContentBlock]


def _msg(text: str) -> _FakeMessage:
    return _FakeMessage(content=[_FakeContentBlock(text=text)])


def _grounding() -> Grounding:
    site = RiskSite(
        file_path="Foo.java",
        line_start=10,
        line_end=20,
        site_kind="prompt_assembly",
        method_name="assemble",
        candidate_risks=["LLM01_Prompt_Injection"],
        snippet="public Prompt assemble(String q) { return new Prompt(q); }",
    )
    entry = OwaspEntry(
        risk_id="LLM01_Prompt_Injection",
        title="Prompt Injection",
        description="user input flows into prompt",
        invariant_to_assert="assembled prompt must not contain breakout payloads",
        exemplar_java="class X {}",
        exemplar_test="@Test void t() {}",
    )
    return Grounding(
        site=site,
        risk_id="LLM01_Prompt_Injection",
        owasp_entry=entry,
        pattern_examples=[],
    )


_GOOD_JSON = (
    '{"risk_id": "LLM01_Prompt_Injection", '
    '"target_lines": [10, 20], '
    '"test_method_source": "@Test void rejectsBreakout() { /* ... */ }", '
    '"assertion_rationale": "checks the assembled prompt does not contain the payload", '
    '"refused": false, '
    '"refusal_reason": null}'
)


# --- extract_json (unit) ---------------------------------------------------


def test_extract_json_strict() -> None:
    assert extract_json(_GOOD_JSON)["risk_id"] == "LLM01_Prompt_Injection"


def test_extract_json_lenient_handles_fences() -> None:
    fenced = "Sure, here you go:\n\n```json\n" + _GOOD_JSON + "\n```\n"
    parsed = extract_json(fenced)
    assert parsed["risk_id"] == "LLM01_Prompt_Injection"
    assert parsed["target_lines"] == [10, 20]


def test_extract_json_lenient_handles_braces_inside_strings() -> None:
    payload = (
        'preface text\n'
        '{"risk_id": "LLM01_Prompt_Injection", '
        '"target_lines": [10, 20], '
        '"test_method_source": "String s = \\"}}\\"; ", '
        '"assertion_rationale": "ok", '
        '"refused": false, '
        '"refusal_reason": null}\n'
        'trailing junk'
    )
    parsed = extract_json(payload)
    assert parsed["test_method_source"] == 'String s = "}}"; '


def test_extract_json_raises_when_no_object_found() -> None:
    with pytest.raises(JsonExtractionError):
        extract_json("just prose here, no JSON object at all")


# --- synthesize (integration of extract + retry + conversion) --------------


async def test_synthesize_strict_json_returns_generated_test() -> None:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=_msg(_GOOD_JSON))

    result = await synthesize(_grounding(), client, owasp_catalog={}, target_class_fqn="com.example.Foo")

    assert isinstance(result, GeneratedTest)
    assert result.refused is False
    assert result.risk_id == "LLM01_Prompt_Injection"
    assert result.target_lines == (10, 20)
    assert "rejectsBreakout" in result.test_method_source
    # No retry happened.
    assert client.complete.await_count == 1


async def test_synthesize_fenced_json_succeeds_first_try() -> None:
    fenced = "```json\n" + _GOOD_JSON + "\n```"
    client = AsyncMock()
    client.complete = AsyncMock(return_value=_msg(fenced))

    result = await synthesize(_grounding(), client, owasp_catalog={}, target_class_fqn="com.example.Foo")

    assert result.refused is False
    assert result.risk_id == "LLM01_Prompt_Injection"
    assert client.complete.await_count == 1


async def test_synthesize_retries_once_then_succeeds() -> None:
    bad = "complete garbage, no JSON here"
    client = AsyncMock()
    client.complete = AsyncMock(side_effect=[_msg(bad), _msg(_GOOD_JSON)])

    result = await synthesize(_grounding(), client, owasp_catalog={}, target_class_fqn="com.example.Foo")

    assert result.refused is False
    assert result.risk_id == "LLM01_Prompt_Injection"
    assert client.complete.await_count == 2

    # The retry should embed the parser error in a follow-up user message.
    second_call_messages: list[dict[str, Any]] = client.complete.await_args_list[1].kwargs["messages"]
    assert second_call_messages[0]["role"] == "user"
    assert second_call_messages[1]["role"] == "assistant"
    assert second_call_messages[1]["content"] == bad
    assert second_call_messages[2]["role"] == "user"
    assert "could not be parsed as JSON" in second_call_messages[2]["content"]


async def test_synthesize_two_failures_returns_refused_generated_test() -> None:
    client = AsyncMock()
    client.complete = AsyncMock(
        side_effect=[_msg("garbage 1"), _msg("still garbage 2")]
    )

    result = await synthesize(_grounding(), client, owasp_catalog={}, target_class_fqn="com.example.Foo")

    assert result.refused is True
    assert result.refusal_reason == "JSON parse failure after retry"
    assert result.risk_id == "LLM01_Prompt_Injection"
    assert result.target_lines == (10, 20)
    assert client.complete.await_count == 2


async def test_synthesize_surfaces_model_refusal() -> None:
    refusal = (
        '{"risk_id": "LLM01_Prompt_Injection", '
        '"target_lines": [0, 0], '
        '"test_method_source": "", '
        '"assertion_rationale": "", '
        '"refused": true, '
        '"refusal_reason": "method has no observable output"}'
    )
    client = AsyncMock()
    client.complete = AsyncMock(return_value=_msg(refusal))

    result = await synthesize(_grounding(), client, owasp_catalog={}, target_class_fqn="com.example.Foo")

    assert result.refused is True
    assert result.refusal_reason == "method has no observable output"
    assert client.complete.await_count == 1
