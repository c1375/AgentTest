"""Risk-site identification rules.

S1 shipped one rule: prompt_assembly -> LLM01 (a method that takes at
least one `String` parameter and constructs any type whose simple name
ends in `PromptTemplate`).

S3 adds two more rules:

- tool_handler -> LLM06 (Excessive Agency): a method annotated `@Tool`
  (any package) with a non-empty `description` attribute. The annotation's
  description is what an LLM treats as ground truth for the tool's
  behavior, so a description vs. implementation mismatch (a write
  inside a tool described as read-only) is the LLM06 surface.

- log_handler -> LLM02 (Sensitive Information Disclosure): a method
  with at least one non-primitive parameter, whose body contains a
  `<logger>.{info,warn,error,debug,...}` call that references one of
  the method's parameters in its argument expressions. The logger
  field is found by sibling-field type name ending in `Logger` or
  `Log` (matches JUL's `java.util.logging.Logger`, SLF4J's
  `org.slf4j.Logger`, Apache Commons `Log`, etc.).

`identify` is `async def` per the layering rule even though no I/O
happens yet — keeps the signature stable when later rules need to
call out.
"""

from dataclasses import dataclass

from javalang.tree import (
    BasicType,
    ClassCreator,
    ClassDeclaration,
    FieldDeclaration,
    MemberReference,
    MethodDeclaration,
    MethodInvocation,
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


# ---------------------------------------------------------------------------
# Step 1: tool_handler -> LLM06
# ---------------------------------------------------------------------------


def _has_tool_annotation_with_description(method: MethodDeclaration) -> bool:
    """True if the method has `@Tool(description = "...non-empty...")`.

    Matches the annotation by simple name, so any-package `@Tool`
    qualifies (Spring AI's `org.springframework.ai.tool.annotation.Tool`
    is what we ship samples for, but the rule is package-agnostic).

    `ann.element` is None for `@Tool` with no args, or a list of
    `ElementValuePair` for `@Tool(name=..., description=...)`. We walk
    the list looking for a `description` pair whose Literal content
    (after stripping the surrounding quotes) is non-blank.
    """
    for ann in (method.annotations or []):
        ann_simple = (ann.name or "").rsplit(".", 1)[-1]
        if ann_simple != "Tool":
            continue
        if ann.element is None:
            return False
        elements = ann.element if isinstance(ann.element, list) else [ann.element]
        for el in elements:
            if getattr(el, "name", None) != "description":
                continue
            raw = getattr(getattr(el, "value", None), "value", "")
            if not isinstance(raw, str):
                continue
            inner = raw.strip('"').strip()
            if inner:
                return True
        return False
    return False


# ---------------------------------------------------------------------------
# Step 2: log_handler -> LLM02
# ---------------------------------------------------------------------------


# Logger method names worth flagging. JUL uses {info, warning, severe,
# fine, finer, finest, log}; SLF4J / Logback use {info, warn, error,
# debug, trace}; Apache Commons {info, warn, error, debug, trace, fatal}.
# We take the union of the ones realistic agent code reaches for at
# INFO+ severity (where PII is most likely to land in a production sink).
_LOGGER_METHODS: frozenset[str] = frozenset({
    "info", "warn", "warning", "error", "severe",
    "debug", "fine", "trace", "fatal", "log",
})


def _collect_logger_field_names(cls: ClassDeclaration) -> set[str]:
    """Names of `cls`'s direct fields whose type's simple name ends in
    `Logger` or `Log`. Catches JUL `Logger`, SLF4J `Logger`, Apache
    Commons `Log`, etc. — without binding to any one logging framework.
    """
    names: set[str] = set()
    for member in cls.body:
        if not isinstance(member, FieldDeclaration):
            continue
        type_name = getattr(member.type, "name", "") or ""
        if type_name.endswith("Logger") or type_name.endswith("Log"):
            for decl in member.declarators:
                names.add(decl.name)
    return names


def _first_segment(qualifier: str | None) -> str | None:
    """First dotted segment of a javalang qualifier string.

    For `inv.subFoo.bar` returns `"inv"`. For an empty / None qualifier
    returns None. javalang stores qualifier strings dotted, not as a
    nested AST.
    """
    if not qualifier:
        return None
    return qualifier.split(".", 1)[0]


def _argument_references_param(arg: Node, param_names: set[str]) -> bool:
    """True if `arg` (an expression subtree) reaches a method parameter.

    Three reference shapes count, mirroring the ways an unsanitized
    parameter realistically flows into a log message:

      - bare identifier (`userInput`)              -> MemberReference.member
      - field/method chain off the parameter
        (`req.tenantId`, `inv.argsJson()`)         -> qualifier's first segment
      - method invocation chain
        (`inv.tool().toUpperCase()`)               -> qualifier's first segment

    Without the qualifier check, we'd miss the common
    `logger.info("x: " + req.field)` / `logger.info(... + inv.method())`
    shapes — false negatives that the LLM02 RequestAuditTrail sample
    in particular surfaces.
    """
    for descendant in _walks_through(arg):
        if isinstance(descendant, MemberReference):
            if descendant.member in param_names:
                return True
            if _first_segment(descendant.qualifier) in param_names:
                return True
        elif isinstance(descendant, MethodInvocation):
            if _first_segment(descendant.qualifier) in param_names:
                return True
    return False


def _has_logger_call_with_user_input(
    method: MethodDeclaration, logger_field_names: set[str]
) -> bool:
    """True if `method` has a non-primitive parameter that flows (via any
    expression) into a `<logger_field>.{info,warn,error,...}(...)` call.
    """
    non_primitive_params = {
        p.name for p in method.parameters if not isinstance(p.type, BasicType)
    }
    if not non_primitive_params:
        return False
    for descendant in _walks_through(method):
        if not isinstance(descendant, MethodInvocation):
            continue
        if descendant.qualifier not in logger_field_names:
            continue
        if descendant.member not in _LOGGER_METHODS:
            continue
        for arg in (descendant.arguments or []):
            if _argument_references_param(arg, non_primitive_params):
                return True
    return False


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


async def identify(
    analyzer_input: AnalyzerInput,
    parser: JavaAstParser | None = None,
) -> list[RiskSite]:
    """Run the full rule set and return the list of detected risk sites.

    Raises whatever `javalang.parse.parse` raises on unparseable Java —
    callers should let that propagate (per `engine/CLAUDE.md`: don't
    catch `Exception` broadly).
    """
    parser = parser or JavalangParser()
    tree = parser.parse(analyzer_input.java_source)
    total_lines = len(analyzer_input.java_source.splitlines())

    sites: list[RiskSite] = []

    # S1 rule: prompt_assembly. Method-local — no class context needed.
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

    # S3 rules: tool_handler + log_handler. Both want sibling-field /
    # sibling-method context, so iterate per class.
    for _path, cls in tree.filter(ClassDeclaration):
        logger_field_names = _collect_logger_field_names(cls)
        for member in cls.body:
            if not isinstance(member, MethodDeclaration):
                continue

            # Step 1 — tool_handler / LLM06
            if _has_tool_annotation_with_description(member):
                line_start, line_end = _line_range(member, total_lines)
                snippet = _extract_snippet(
                    analyzer_input.java_source, line_start, line_end
                )
                sites.append(
                    RiskSite(
                        file_path=analyzer_input.file_path,
                        line_start=line_start,
                        line_end=line_end,
                        site_kind="tool_handler",
                        method_name=member.name,
                        candidate_risks=["LLM06_Excessive_Agency"],
                        snippet=snippet,
                    )
                )

            # Step 2 — log_handler / LLM02
            if logger_field_names and _has_logger_call_with_user_input(
                member, logger_field_names
            ):
                line_start, line_end = _line_range(member, total_lines)
                snippet = _extract_snippet(
                    analyzer_input.java_source, line_start, line_end
                )
                sites.append(
                    RiskSite(
                        file_path=analyzer_input.file_path,
                        line_start=line_start,
                        line_end=line_end,
                        site_kind="log_handler",
                        method_name=member.name,
                        candidate_risks=["LLM02_Sensitive_Information_Disclosure"],
                        snippet=snippet,
                    )
                )

    return sites
