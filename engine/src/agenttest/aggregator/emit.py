"""Combine surviving validated tests into one Java class.

Each generator output is a method body (`@Test void name() { ... }`).
The aggregator:

  - Concatenates all surviving methods.
  - Parses `import` statements out of each method's source (some
    generators emit fully-qualified names instead, which is fine —
    we just don't double-emit imports).
  - Deduplicates imports; first-writer-wins on conflict, with an
    INFO log noting the loser. Conflicts are unlikely with the
    JUnit 5 + AssertJ surface used in S2.
  - Emits a header comment listing the OWASP risk IDs covered and
    the standing reminder that generated tests are advisory.
  - When the validated list is empty, emits a class with just the
    header and an explanatory note. The pipeline always produces
    SOMETHING parseable so the CLI's `write_text` always succeeds.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from agenttest.contracts import (
    OwaspRiskId,
    RiskSite,
    TestClassEmission,
    ValidatedTest,
)

logger = logging.getLogger(__name__)


_IMPORT_RE = re.compile(
    r"^\s*import\s+(?:static\s+)?[\w.]+(?:\s*\.\s*\*)?\s*;",
    re.MULTILINE,
)


_TEST_ANNOTATION_RE = re.compile(
    r"^\s*@(?:org\.junit\.jupiter\.api\.)?Test\b",
    re.MULTILINE,
)


@dataclass(frozen=True)
class _SplitMethod:
    """Per-method extraction: imports + the method source minus imports."""

    imports: list[str]
    method_source: str


def _split_imports(method_source: str) -> _SplitMethod:
    """Pull `import ...;` lines out of `method_source`.

    Generators are instructed to emit method bodies only, but
    sometimes they include imports inline (especially when using
    AssertJ's static `assertThat`). We strip and aggregate them so
    the wrapped class file ends up with a single deduplicated import
    block.

    Scope: only the prelude before the first `@Test` annotation is
    scanned. This prevents a string literal like `"import x;"` inside
    the method body from being hoisted out as if it were a real
    import declaration.
    """
    test_match = _TEST_ANNOTATION_RE.search(method_source)
    if test_match:
        prelude = method_source[: test_match.start()]
        rest = method_source[test_match.start() :]
    else:
        prelude = method_source
        rest = ""
    imports = [m.group(0).strip() for m in _IMPORT_RE.finditer(prelude)]
    cleaned_prelude = _IMPORT_RE.sub("", prelude).strip()
    if cleaned_prelude and rest:
        cleaned = f"{cleaned_prelude}\n\n{rest}".strip()
    else:
        cleaned = (cleaned_prelude + rest).strip()
    return _SplitMethod(imports=imports, method_source=cleaned)


def _dedup_imports(method_imports: list[list[str]]) -> list[str]:
    """First-writer-wins dedup; INFO-log when a dropped duplicate differs from the kept line."""
    seen: dict[str, str] = {}  # canonical key → original line
    for imports_for_method in method_imports:
        for line in imports_for_method:
            key = re.sub(r"\s+", " ", line).strip().rstrip(";")
            if key in seen:
                if seen[key] != line:
                    logger.info(
                        "aggregator: dedup_imports kept %r, dropped %r",
                        seen[key],
                        line,
                    )
                continue
            # If a static and non-static of the same target both appear,
            # keep both — they're different keys above.
            seen[key] = line
    return list(seen.values())


_BASE_IMPORTS: tuple[str, ...] = (
    "import org.junit.jupiter.api.Test;",
    "import static org.assertj.core.api.Assertions.assertThat;",
)


_ADVISORY_REMINDER = (
    "Generated tests are advisory. A human MUST review every test before it "
    "lands in src/test/java."
)


def _build_header(
    target_class_name: str,
    risks_covered: list[OwaspRiskId],
    *,
    no_tests: bool,
) -> str:
    """Build the `/* ... */` header comment for the emitted class."""
    risks = (
        "\n".join(f" *   - {r}" for r in risks_covered)
        if risks_covered
        else " *   (none — no tests survived validation)"
    )
    return (
        "/*\n"
        f" * AgentTest-generated agent tests for {target_class_name}.\n"
        " *\n"
        " * OWASP risks covered:\n"
        f"{risks}\n"
        " *\n"
        f" * {_ADVISORY_REMINDER}\n"
        + (
            " *\n * NOTE: no tests survived the validator gate on this run.\n"
            if no_tests
            else ""
        )
        + " */\n"
    )


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else line for line in text.split("\n"))


def _output_path_for(input_dir: str, target_class_name: str) -> str:
    return f"{input_dir}/{target_class_name}AgentGenTest.java"


def aggregate(
    validated: list[ValidatedTest],
    target_class_name: str,
    target_package: str,
    *,
    refused_sites: list[tuple[RiskSite, str]] | None = None,
    output_path: str,
) -> TestClassEmission:
    """Combine surviving validated tests into a single Java class.

    Parameters
    ----------
    validated
        Surviving tests from the validator gate.
    target_class_name
        Bare class name of the target (e.g., `RestaurantPromptAssembler`).
        The emitted class is named `<target_class_name>AgentGenTest`.
    target_package
        Package name for the emitted class. Should match the target's
        package so the test can `new <target_class_name>()` without
        importing it.
    refused_sites
        Threaded through into the `TestClassEmission` for the CLI to
        report. Optional — defaults to empty.
    output_path
        Where the CLI / pipeline plans to write this file. Threaded
        into the emission for the CLI's `write_text(...)` call.
    """
    refused_sites = refused_sites if refused_sites is not None else []
    test_class_name = f"{target_class_name}AgentGenTest"

    risks_covered: list[OwaspRiskId] = []
    seen_risk: set[OwaspRiskId] = set()
    method_blocks: list[str] = []
    method_imports: list[list[str]] = []

    for v in validated:
        split = _split_imports(v.test.test_method_source)
        method_imports.append(split.imports)
        method_blocks.append(split.method_source)
        if v.test.risk_id not in seen_risk:
            seen_risk.add(v.test.risk_id)
            risks_covered.append(v.test.risk_id)

    # Always include the JUnit + AssertJ baseline imports — the
    # wrapper relies on them, and dedup will collapse duplicates if
    # the model also emitted them.
    method_imports.insert(0, list(_BASE_IMPORTS))
    imports = _dedup_imports(method_imports)

    no_tests = not method_blocks
    header = _build_header(target_class_name, risks_covered, no_tests=no_tests)

    package_line = f"package {target_package};\n\n" if target_package else ""
    import_block = "\n".join(imports) + "\n\n" if imports else ""

    body_methods = "\n\n".join(_indent(m, "    ") for m in method_blocks)

    if no_tests:
        body = (
            "    // No generator output survived the validator gate on this run.\n"
            "    // See the CLI's refused-sites report for per-site reasons.\n"
        )
    else:
        body = body_methods + "\n"

    java_source = (
        header
        + package_line
        + import_block
        + f"class {test_class_name} {{\n\n"
        + body
        + "\n}\n"
    )

    return TestClassEmission(
        target_class_name=target_class_name,
        output_path=output_path,
        java_source=java_source,
        risks_covered=risks_covered,
        refused_sites=refused_sites,
    )
