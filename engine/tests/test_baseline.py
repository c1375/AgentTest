"""Unit tests for baseline.synthesize.synthesize_baseline.

All cases run with a mocked AgentClient — no real Anthropic call.
The baseline is one prompt -> one Java class output, so the surface
under test is small: prompt content, fence extraction, parse-flag,
multi-text-block concatenation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock

import pytest

from agenttest.baseline.synthesize import (
    BASELINE_PROMPT_TEMPLATE,
    _extract_java,
    synthesize_baseline,
)
from agenttest.contracts import BaselineEmission

# ---------------------------------------------------------------------------
# Anthropic Message fakes
# ---------------------------------------------------------------------------


@dataclass
class _FakeTextBlock:
    """Mimics anthropic.types.TextBlock — needs `.type` and `.text` attrs."""

    text: str
    type: str = "text"


@dataclass
class _FakeMessage:
    """Mimics anthropic.types.Message — needs `.content` list of blocks."""

    content: list[_FakeTextBlock] = field(default_factory=list)


def _msg(*texts: str) -> _FakeMessage:
    return _FakeMessage(content=[_FakeTextBlock(text=t) for t in texts])


# ---------------------------------------------------------------------------
# _extract_java (unit)
# ---------------------------------------------------------------------------


def test_extract_java_returns_fence_contents() -> None:
    output = "Sure, here is the test class:\n\n```java\nclass T {}\n```\n"
    assert _extract_java(output) == "class T {}"


def test_extract_java_picks_longest_fence() -> None:
    """If the model includes a small example fence before the answer,
    the longest fence should win."""
    output = (
        "Example shape:\n```java\n// short\n```\n\n"
        "Actual answer:\n```java\nclass Long {\n  void m() {}\n  void n() {}\n}\n```\n"
    )
    extracted = _extract_java(output)
    assert "class Long" in extracted
    assert "// short" not in extracted


def test_extract_java_handles_unmarked_fence() -> None:
    """Some models emit ``` without the `java` language tag."""
    output = "```\nclass T {}\n```"
    assert _extract_java(output) == "class T {}"


def test_extract_java_treats_unfenced_output_as_java() -> None:
    """No fence at all → return the whole output, stripped."""
    raw = "  class T {}  \n"
    assert _extract_java(raw) == "class T {}"


# ---------------------------------------------------------------------------
# synthesize_baseline (integration)
# ---------------------------------------------------------------------------


_GOOD_TEST_CLASS = """\
package com.example.spring;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class FooAgentGenTest {
    @Test
    void smoke() {
        assertThat(true).isTrue();
    }
}
"""


async def test_synthesize_baseline_extracts_fence_and_parses() -> None:
    fenced = "```java\n" + _GOOD_TEST_CLASS + "```"
    client = AsyncMock()
    client.complete = AsyncMock(return_value=_msg(fenced))

    result = await synthesize_baseline(
        java_source="class Foo {}",
        target_class_name="Foo",
        target_package="com.example.spring",
        client=client,
    )

    assert isinstance(result, BaselineEmission)
    assert result.target_class_name == "Foo"
    assert "class FooAgentGenTest" in result.java_source
    assert "```" not in result.java_source, "fence must be stripped"
    assert result.parseable is True


async def test_synthesize_baseline_accepts_unfenced_java() -> None:
    """Some models return raw Java with no fence — still works."""
    client = AsyncMock()
    client.complete = AsyncMock(return_value=_msg(_GOOD_TEST_CLASS))

    result = await synthesize_baseline(
        java_source="class Foo {}",
        target_class_name="Foo",
        target_package="com.example.spring",
        client=client,
    )

    assert result.parseable is True
    assert "class FooAgentGenTest" in result.java_source


async def test_synthesize_baseline_concatenates_multi_text_blocks() -> None:
    """A two-block response (rationale + code) is reassembled before
    fence extraction, so the code block is found."""
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=_msg(
            "Here's my analysis: the class needs prompt-injection coverage.\n",
            "```java\n" + _GOOD_TEST_CLASS + "```",
        )
    )

    result = await synthesize_baseline(
        java_source="class Foo {}",
        target_class_name="Foo",
        target_package="com.example.spring",
        client=client,
    )

    assert result.parseable is True
    assert "class FooAgentGenTest" in result.java_source


async def test_synthesize_baseline_flags_unparseable_output() -> None:
    """Garbage output -> parseable=False, java_source preserved for diagnostics."""
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=_msg("I refuse to write tests for this class.")
    )

    result = await synthesize_baseline(
        java_source="class Foo {}",
        target_class_name="Foo",
        target_package="com.example.spring",
        client=client,
    )

    assert result.parseable is False
    assert "I refuse" in result.java_source, "raw output preserved on parse failure"


async def test_synthesize_baseline_passes_target_package_into_prompt() -> None:
    """The prompt must thread target_package + target_class_name + 'no Mockito'."""
    client = AsyncMock()
    client.complete = AsyncMock(return_value=_msg(_GOOD_TEST_CLASS))

    await synthesize_baseline(
        java_source="class Foo {}",
        target_class_name="Foo",
        target_package="com.example.spring",
        client=client,
    )

    user_msg = client.complete.await_args.kwargs["messages"][0]["content"]
    assert "com.example.spring" in user_msg
    assert "Foo" in user_msg
    assert "FooAgentGenTest" in user_msg
    assert "Mockito" in user_msg, "no-Mockito constraint must be present per Step 0"


def test_baseline_prompt_template_mentions_required_constraints() -> None:
    """Lock the constraints from sprint-3.md Step 0 against drift."""
    assert "Mockito" in BASELINE_PROMPT_TEMPLATE
    assert "JUnit 5" in BASELINE_PROMPT_TEMPLATE
    assert "AssertJ" in BASELINE_PROMPT_TEMPLATE
    assert "{target_package}" in BASELINE_PROMPT_TEMPLATE
    assert "{target_class_name}" in BASELINE_PROMPT_TEMPLATE
    assert "{src}" in BASELINE_PROMPT_TEMPLATE
