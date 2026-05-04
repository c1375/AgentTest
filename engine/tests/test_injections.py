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

from eval.injections import (  # noqa: E402
    Llm01RemoveSanitization,
    Llm02DropRedaction,
    Llm06AddUnannouncedWrite,
)

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


# ---------------------------------------------------------------------------
# LLM06: un-comment `// LLM06_INJECT: <code>` markers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sample_filename",
    [
        "MenuMcpServer.java",
        "WeatherTool.java",
    ],
)
def test_llm06_injection_uncomments_marker(sample_filename: str) -> None:
    """Each marker line `// LLM06_INJECT: X` becomes the bare statement `X`."""
    java_source = (SAMPLES_DIR / sample_filename).read_text(encoding="utf-8")
    injected = Llm06AddUnannouncedWrite().apply(java_source)

    assert injected != java_source, "injection produced no change"
    assert "// LLM06_INJECT:" not in injected, "marker comment must be gone"


def test_llm06_injection_preserves_indent() -> None:
    """The replacement statement keeps the marker line's leading whitespace."""
    snippet = "class X {\n    void m() {\n        // LLM06_INJECT: foo();\n        return;\n    }\n}\n"
    injected = Llm06AddUnannouncedWrite().apply(snippet)
    assert "        foo();" in injected, "expected 8-space-indented foo() call"


def test_llm06_injection_handles_multiple_markers() -> None:
    """Multiple markers in one file all get uncommented in a single pass."""
    snippet = (
        "class X {\n"
        "    void a() {\n"
        "        // LLM06_INJECT: counter.inc();\n"
        "    }\n"
        "    void b() {\n"
        "        // LLM06_INJECT: cache.put(k, v);\n"
        "    }\n"
        "}\n"
    )
    injected = Llm06AddUnannouncedWrite().apply(snippet)
    assert "counter.inc();" in injected
    assert "cache.put(k, v);" in injected
    assert "// LLM06_INJECT:" not in injected


@pytest.mark.parametrize(
    "sample_filename",
    [
        "MenuMcpServer.java",
        "WeatherTool.java",
    ],
)
def test_llm06_injection_preserves_java_parseability(sample_filename: str) -> None:
    """Buggy variant must still parse — we only un-comment a single line."""
    java_source = (SAMPLES_DIR / sample_filename).read_text(encoding="utf-8")
    injected = Llm06AddUnannouncedWrite().apply(java_source)
    tree = javalang_parse.parse(injected)
    assert tree is not None


def test_llm06_injection_raises_when_no_marker() -> None:
    """No LLM06_INJECT marker anywhere → ValueError."""
    java_source = "class Plain { void m() { return; } }\n"
    with pytest.raises(ValueError, match="not applicable"):
        Llm06AddUnannouncedWrite().apply(java_source)


# ---------------------------------------------------------------------------
# LLM02: strip redactPii / sha256 wrapper calls to bare arguments
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sample_filename, expected_helper",
    [
        ("AgentLogger.java", "redactPii"),
        ("RequestAuditTrail.java", "sha256"),
    ],
)
def test_llm02_injection_strips_helper_call(
    sample_filename: str, expected_helper: str
) -> None:
    """The helper call inside the log statement is gone after injection.

    Specifically: the bare argument (e.g., `req` or `inv.argsJson()`)
    appears in the log statement where the wrapper used to be. Helper
    declarations elsewhere in the file are unaffected (we only strip
    CALL sites, not definitions).
    """
    java_source = (SAMPLES_DIR / sample_filename).read_text(encoding="utf-8")
    injected = Llm02DropRedaction().apply(java_source)

    assert injected != java_source, "injection produced no change"

    # The log line must no longer wrap its argument in the helper.
    for line in injected.splitlines():
        if "logger.info" in line:
            assert f"{expected_helper}(" not in line, (
                f"helper {expected_helper}() should be stripped from log line; "
                f"got: {line!r}"
            )


@pytest.mark.parametrize(
    "sample_filename",
    [
        "AgentLogger.java",
        "RequestAuditTrail.java",
    ],
)
def test_llm02_injection_preserves_java_parseability(sample_filename: str) -> None:
    """Buggy variant must still parse — we only rewrote a call expression."""
    java_source = (SAMPLES_DIR / sample_filename).read_text(encoding="utf-8")
    injected = Llm02DropRedaction().apply(java_source)
    tree = javalang_parse.parse(injected)
    assert tree is not None


def test_llm02_injection_handles_nested_parens_in_arg() -> None:
    """Argument expressions with their own parens (e.g., method calls) are extracted whole."""
    snippet = (
        "class X {\n"
        "  void m(I inv) {\n"
        "    log.info(\"x: \" + sha256(inv.argsJson()));\n"
        "  }\n"
        "  static String sha256(String s) { return s; }\n"
        "}\n"
    )
    injected = Llm02DropRedaction().apply(snippet)
    # The argument `inv.argsJson()` must survive intact.
    assert "inv.argsJson()" in injected
    assert "sha256(inv.argsJson())" not in injected
    # Helper definition (different position from the call site) is
    # not modified — the call inside the body still references sha256.
    # Actually, the definition *itself* contains "sha256(String s)"
    # which is NOT a call (it's the declaration), so the helper-call
    # finder shouldn't match it. Verify:
    assert "static String sha256(String s)" in injected


def test_llm02_injection_skips_substring_helper_names() -> None:
    """`mySha256(...)` shouldn't be matched as a sha256 call (word-boundary check)."""
    snippet = (
        "class X {\n"
        "  void m() { log.info(mySha256(\"x\")); }\n"
        "  static String mySha256(String s) { return s; }\n"
        "}\n"
    )
    with pytest.raises(ValueError, match="not applicable"):
        Llm02DropRedaction().apply(snippet)


def test_llm02_injection_raises_when_no_known_helper() -> None:
    """No call to any known helper → ValueError."""
    java_source = "class Plain { void m() { return; } }\n"
    with pytest.raises(ValueError, match="not applicable"):
        Llm02DropRedaction().apply(java_source)
