"""Risk-site identification rules.

S1 ships ONE rule: a method that takes at least one `String` parameter and
constructs any type whose simple name ends in `PromptTemplate` is a
candidate prompt-assembly site for LLM01 (Prompt Injection). This matches
Spring AI's `PromptTemplate`, `SystemPromptTemplate`, `UserPromptTemplate`,
etc. More rules (tool_handler, mcp_endpoint, tenant_boundary, retry_config)
land in S2+.

`identify` is `async def` per the layering rule even though no I/O happens
yet — keeps the signature stable when later rules need to call out.
"""

from dataclasses import dataclass

from javalang.tree import (
    ClassCreator,
    MethodDeclaration,
    Node,
)

from agenttest.analyzer.ast_parser import JavaAstParser, JavalangParser
from agenttest.contracts import RiskSite


@dataclass
class AnalyzerInput:
    java_source: str
    file_path: str


def _walks_through(node: Node):
    """Yield every Node in a `javalang` subtree (including the root)."""
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from _walks_through(child)
        elif isinstance(child, (list, tuple)):
            for item in child:
                if isinstance(item, Node):
                    yield from _walks_through(item)


def _line_range(method: MethodDeclaration, total_lines: int) -> tuple[int, int]:
    """Best-effort line range for a method body.

    `javalang` only attaches `position` to a subset of nodes (those backed
    by a token), so we walk the subtree and take min/max of the positions
    we find. End-line is conservative — the closing brace is past the last
    token, so we add 1, clamped to the file length.
    """
    line_start: int | None = method.position.line if method.position else None
    line_end: int | None = line_start

    for descendant in _walks_through(method):
        pos = getattr(descendant, "position", None)
        if pos is None:
            continue
        if line_start is None or pos.line < line_start:
            line_start = pos.line
        if line_end is None or pos.line > line_end:
            line_end = pos.line

    if line_start is None:
        # No position info at all — fall back to "whole file" so we still
        # emit a record rather than silently dropping the site.
        return 1, total_lines

    return line_start, min(line_end + 1 if line_end else line_start, total_lines)


def _has_string_parameter(method: MethodDeclaration) -> bool:
    for param in method.parameters:
        type_node = param.type
        if getattr(type_node, "name", None) == "String":
            return True
    return False


def _constructs_prompt_template(method: MethodDeclaration) -> bool:
    for descendant in _walks_through(method):
        if isinstance(descendant, ClassCreator):
            type_name = getattr(descendant.type, "name", "") or ""
            if type_name.endswith("PromptTemplate"):
                return True
    return False


def _extract_snippet(java_source: str, line_start: int, line_end: int) -> str:
    lines = java_source.splitlines()
    # javalang lines are 1-indexed; clamp defensively.
    start = max(line_start - 1, 0)
    end = min(line_end, len(lines))
    return "\n".join(lines[start:end])


async def identify(
    analyzer_input: AnalyzerInput,
    parser: JavaAstParser | None = None,
) -> list[RiskSite]:
    """Run S1's rule set and return the list of detected risk sites.

    Raises whatever `javalang.parse.parse` raises on unparseable Java —
    callers should let that propagate (per `engine/CLAUDE.md`: don't catch
    `Exception` broadly).
    """
    parser = parser or JavalangParser()
    tree = parser.parse(analyzer_input.java_source)
    total_lines = len(analyzer_input.java_source.splitlines())

    sites: list[RiskSite] = []
    for _path, method in tree.filter(MethodDeclaration):
        if not _has_string_parameter(method):
            continue
        if not _constructs_prompt_template(method):
            continue

        line_start, line_end = _line_range(method, total_lines)
        snippet = _extract_snippet(analyzer_input.java_source, line_start, line_end)

        sites.append(
            RiskSite(
                file_path=analyzer_input.file_path,
                line_start=line_start,
                line_end=line_end,
                site_kind="prompt_assembly",
                method_name=method.name,
                candidate_risks=["LLM01_Prompt_Injection"],
                snippet=snippet,
            )
        )

    return sites
