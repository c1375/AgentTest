"""LLM02 injection: strip a privacy-preserving helper call to a passthrough.

Models a realistic LLM02 regression: a developer "simplifies" the
logging path by removing a `redactPii(...)` or `sha256(...)` wrapper,
not realizing the wrapper was load-bearing for keeping sentinels out
of the log sink.

Operation: every call to one of the known helper names is replaced by
the helper's argument expression. Example:

    logger.info("Handling: " + redactPii(req));

becomes:

    logger.info("Handling: " + req);

and:

    logger.info("audit: " + sha256(inv.argsJson()));

becomes:

    logger.info("audit: " + inv.argsJson());

Both rewrites compile because Java's `+` operator on (String, Object)
performs implicit toString. The bare expression flows verbatim into
the log message, leaking any embedded sentinel.

Helper-name list is fixed at construction time and matched word-bounded
so a substring like `sha256Test` doesn't trigger. Multiple call sites
across the file are all stripped in one pass (right-to-left so earlier
positions don't shift).
"""

from __future__ import annotations

import re

from .base import Injection

# Names of privacy-preserving wrappers the injection knows how to strip.
# Add new names here as new LLM02 samples introduce new wrapper helpers
# (e.g., `mask`, `tokenize`, etc.).
_HELPER_NAMES: tuple[str, ...] = ("redactPii", "sha256")


def _find_matching_paren(source: str, open_pos: int) -> int:
    """Return the index of the `)` matching the `(` at `open_pos`.

    Skips Java single-line string literals so embedded `(`/`)` inside
    `"..."` don't break the depth count. Does not handle text blocks
    (`\"\"\"`); fixtures shouldn't use them.
    """
    if source[open_pos] != "(":
        raise AssertionError(f"expected '(' at position {open_pos}")
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
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unmatched opening paren")


# Keywords that legitimately precede an expression in Java. When the
# token before a helper name is one of these, the helper invocation is
# a real call (e.g., `return redactPii(req);`), not a method
# declaration's return type.
_JAVA_KEYWORDS_BEFORE_EXPR: frozenset[str] = frozenset({
    "return", "throw", "yield", "assert", "new",
    "if", "while", "for", "do", "case", "else",
    "finally", "try", "synchronized",
})


def _looks_like_method_decl(source: str, helper_start: int) -> bool:
    """True if the position right before `helper_start` looks like a
    method-declaration return type — i.e., an identifier that is NOT
    one of the Java keywords that legitimately precedes an expression.

    Without this check, `static String redactPii(String s) { ... }` would
    be matched as if it were a call site `redactPii(String s)`, and the
    "argument" `String s` would be substituted in — corrupting the
    helper's own declaration.
    """
    scan = helper_start - 1
    while scan >= 0 and source[scan] in (" ", "\t"):
        scan -= 1
    if scan < 0:
        return False
    if not (source[scan].isalnum() or source[scan] == "_"):
        return False
    end = scan + 1
    while scan >= 0 and (source[scan].isalnum() or source[scan] == "_"):
        scan -= 1
    word = source[scan + 1 : end]
    return word not in _JAVA_KEYWORDS_BEFORE_EXPR


def _find_call_sites(source: str, helper_name: str) -> list[tuple[int, int, str]]:
    """Find all `helper_name(<expr>)` call sites in `source`.

    Returns a list of (call_start, call_end_exclusive, expr_text). The
    `\\b` boundaries prevent partial matches like `mySha256(...)`, and
    `_looks_like_method_decl` skips the helper's own declaration.
    """
    pattern = re.compile(r"\b" + re.escape(helper_name) + r"\s*\(")
    sites: list[tuple[int, int, str]] = []
    for match in pattern.finditer(source):
        if _looks_like_method_decl(source, match.start()):
            continue
        open_paren = match.end() - 1  # position of `(`
        close_paren = _find_matching_paren(source, open_paren)
        expr = source[open_paren + 1 : close_paren]
        sites.append((match.start(), close_paren + 1, expr))
    return sites


class Llm02DropRedaction(Injection):
    """Replace every `<helper>(<expr>)` call with `<expr>` for known helpers."""

    name = "llm02_drop_redaction"

    def apply(self, java_source: str) -> str:
        all_sites: list[tuple[int, int, str]] = []
        for helper in _HELPER_NAMES:
            all_sites.extend(_find_call_sites(java_source, helper))

        if not all_sites:
            raise ValueError(
                f"no calls to any of {_HELPER_NAMES!r} found — "
                "this injection is not applicable to the given source"
            )

        # Replace right-to-left so earlier replacements don't shift the
        # indices of later sites.
        all_sites.sort(key=lambda site: site[0], reverse=True)
        out = java_source
        for start, end, expr in all_sites:
            out = out[:start] + expr + out[end:]
        return out
