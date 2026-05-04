"""Unit tests for the OWASP catalog loader (`retrieval/owasp.py`)."""

from pathlib import Path

import pytest

from agenttest.retrieval.owasp import load_owasp

ENGINE_ROOT = Path(__file__).resolve().parent.parent
REAL_CATALOG = ENGINE_ROOT / "configs" / "owasp.yaml"


def test_load_owasp_real_catalog_has_llm01_with_all_fields() -> None:
    catalog = load_owasp(REAL_CATALOG)

    assert "LLM01_Prompt_Injection" in catalog
    entry = catalog["LLM01_Prompt_Injection"]

    assert entry.risk_id == "LLM01_Prompt_Injection"
    assert entry.title.strip() != ""
    assert entry.description.strip() != ""
    assert entry.invariant_to_assert.strip() != ""
    assert entry.exemplar_java.strip() != ""
    assert entry.exemplar_test.strip() != ""


def test_load_owasp_invariant_mentions_breakout_payloads() -> None:
    """Sanity-check the LLM01 invariant has the canonical payload list.

    The generator prompt threads `invariant_to_assert` verbatim, so a
    regression that drops the payload list would silently weaken
    every generated test.
    """
    catalog = load_owasp(REAL_CATALOG)
    invariant = catalog["LLM01_Prompt_Injection"].invariant_to_assert.lower()
    assert "ignore" in invariant or "breakout" in invariant or "[/inst]" in invariant


def test_load_owasp_llm06_exemplar_uses_qualified_nested_names() -> None:
    """LLM06 sample collaborators are static-nested in MenuMcpServer.

    The exemplar test must reference them as `MenuMcpServer.InMemoryViewCounter`
    (not bare `InMemoryViewCounter`) so Sonnet copies the qualified-name
    pattern. A silent regression that strips the qualification would
    look fine in the YAML but cause every LLM06 generated test to
    COMPILE_FAIL — the failure would surface as recall=0 with no
    obvious cause.
    """
    catalog = load_owasp(REAL_CATALOG)
    exemplar = catalog["LLM06_Excessive_Agency"].exemplar_test
    assert "MenuMcpServer.InMemoryViewCounter" in exemplar
    assert "MenuMcpServer.InMemoryMenuRepo" in exemplar
    assert "MenuMcpServer.SearchRequest" in exemplar


def test_load_owasp_missing_field_raises_valueerror(tmp_path: Path) -> None:
    """Synthetic YAML with `invariant_to_assert` missing → ValueError naming the field."""
    bad = tmp_path / "owasp.yaml"
    bad.write_text(
        "- risk_id: LLM99_Synthetic\n"
        "  title: Synthetic\n"
        "  description: |\n"
        "    only here for the test\n"
        "  exemplar_java: |\n"
        "    class X {}\n"
        "  exemplar_test: |\n"
        "    @Test void t() {}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invariant_to_assert"):
        load_owasp(bad)


def test_load_owasp_empty_field_raises_valueerror(tmp_path: Path) -> None:
    bad = tmp_path / "owasp.yaml"
    bad.write_text(
        "- risk_id: LLM99_Synthetic\n"
        "  title: Synthetic\n"
        "  description: |\n"
        "    \n"
        "  invariant_to_assert: |\n"
        "    must be non-empty\n"
        "  exemplar_java: |\n"
        "    class X {}\n"
        "  exemplar_test: |\n"
        "    @Test void t() {}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="description"):
        load_owasp(bad)


def test_load_owasp_non_list_root_raises(tmp_path: Path) -> None:
    """A top-level dict instead of a list must produce a clear error."""
    bad = tmp_path / "owasp.yaml"
    bad.write_text(
        "LLM01_Prompt_Injection:\n"
        "  title: dict-shaped (wrong)\n"
        "  description: should be a list of entries\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="root to be a list"):
        load_owasp(bad)


def test_load_owasp_duplicate_risk_id_raises(tmp_path: Path) -> None:
    bad = tmp_path / "owasp.yaml"
    bad.write_text(
        "- risk_id: LLM01_Prompt_Injection\n"
        "  title: A\n"
        "  description: a\n"
        "  invariant_to_assert: a\n"
        "  exemplar_java: a\n"
        "  exemplar_test: a\n"
        "- risk_id: LLM01_Prompt_Injection\n"
        "  title: B\n"
        "  description: b\n"
        "  invariant_to_assert: b\n"
        "  exemplar_java: b\n"
        "  exemplar_test: b\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate risk_id"):
        load_owasp(bad)
