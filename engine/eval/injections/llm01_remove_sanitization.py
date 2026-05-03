"""LLM01 injection: neutralize a `sanitize(String)` helper to a passthrough.

Models a realistic LLM01 regression: a developer refactors a sanitization
helper and accidentally short-circuits it (e.g., during a "simplify" pass),
letting raw user input flow into the prompt template unmodified.

Operates on the source by:
  1. Locating the `static String sanitize(String <param>)` declaration.
  2. Replacing its body with `return <param>;`.

The brace-matching scan skips Java string literals so embedded `{` / `}`
characters inside regex patterns don't confuse the search.
"""

from __future__ import annotations

import re

from .base import Injection

_SIGNATURE_RE = re.compile(
    r"""(?P<signature>
        (?:private|public|protected)?\s*
        (?:static\s+)?
        String\s+sanitize\s*\(\s*String\s+(?P<param>\w+)\s*\)\s*
    )\{""",
    re.VERBOSE,
)


def _find_matching_brace(source: str, open_pos: int) -> int:
    """Return the index of the `}` matching the `{` at `open_pos`.

    Skips Java single-line string literals so embedded `{`/`}` inside
    `"..."` don't break the depth count. Does not handle text blocks
    (`\"\"\"`); fixtures shouldn't use them.
    """
    if source[open_pos] != "{":
        raise AssertionError(f"expected '{{' at position {open_pos}")
    depth = 1
    i = open_pos + 1
    while i < len(source):
        ch = source[i]
        if ch == '"':
            i += 1
            while i < len(source) and source[i] != '"':
                if source[i] == "\\":
                    i += 2  # skip escape sequence
                else:
                    i += 1
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unmatched opening brace")


class Llm01RemoveSanitization(Injection):
    """Replace the body of `sanitize(String input)` with `return input;`."""

    name = "llm01_remove_sanitization"

    def apply(self, java_source: str) -> str:
        match = _SIGNATURE_RE.search(java_source)
        if match is None:
            raise ValueError(
                "no `String sanitize(String <param>)` helper found — "
                "this injection is not applicable to the given source"
            )

        param_name = match.group("param")
        # match.end() points one past the `{` (the `\{` at the end of the
        # pattern consumes it). Step back one to land ON the `{`.
        open_brace_pos = match.end() - 1
        close_brace_pos = _find_matching_brace(java_source, open_brace_pos)

        replacement_body = "{\n        return " + param_name + ";\n    }"
        return (
            java_source[:open_brace_pos]
            + replacement_body
            + java_source[close_brace_pos + 1:]
        )
