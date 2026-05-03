"""Tests for OWASP risk injection scripts (engine/eval/injections/)."""

import sys
from pathlib import Path

import pytest
from javalang import parse as javalang_parse

# eval/ lives at engine/eval/, not under src/agenttest/. Make it
# importable from this test file by extending sys.path to the engine
# root (one directory above tests/).
ENGINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_ROOT))

from eval.injections import Llm01RemoveSanitization  # noqa: E402

SAMPLES_DIR = ENGINE_ROOT / "eval" / "samples" / "spring_ai"


@pytest.mark.parametrize(
    "sample_filename",
    [
        "RestaurantPromptAssembler.java",
        "EmailDraftingAssembler.java",
    ],
)
def test_llm01_injection_neutralizes_sanitize(sample_filename: str) -> None:
    """The injection replaces sanitize()'s body with `return <param>;`."""
    java_source = (SAMPLES_DIR / sample_filename).read_text(encoding="utf-8")
    injected = Llm01RemoveSanitization().apply(java_source)

    assert injected != java_source, "injection produced no change"
    assert "return input;" in injected, "expected `return input;` in injected sanitize body"
    # The original sanitization regex calls should be gone from sanitize().
    # (Other replaceAll calls elsewhere in the class would still appear,
    # but our samples only use it inside sanitize().)
    assert "replaceAll" not in injected, (
        "expected the original replaceAll-based sanitization to be removed"
    )


@pytest.mark.parametrize(
    "sample_filename",
    [
        "RestaurantPromptAssembler.java",
        "EmailDraftingAssembler.java",
    ],
)
def test_llm01_injection_preserves_java_parseability(sample_filename: str) -> None:
    """Buggy variant must still parse — we only mutated a method body."""
    java_source = (SAMPLES_DIR / sample_filename).read_text(encoding="utf-8")
    injected = Llm01RemoveSanitization().apply(java_source)
    tree = javalang_parse.parse(injected)
    assert tree is not None


def test_llm01_injection_raises_when_no_sanitize_helper() -> None:
    """Applying the injection to a class without sanitize() must fail loudly."""
    java_source = """\
package com.example;

public class Plain {
    public String greet(String name) {
        return "hi " + name;
    }
}
"""
    with pytest.raises(ValueError, match="not applicable"):
        Llm01RemoveSanitization().apply(java_source)
