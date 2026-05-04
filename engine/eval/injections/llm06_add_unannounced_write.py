"""LLM06 injection: un-comment a `// LLM06_INJECT: <code>` hint line.

Models a realistic LLM06 regression: a developer adds an unannounced
side-effect (a counter increment, cache write, audit log) inside a
method whose @Tool description claims read-only / stateless behavior.

Why a hint comment instead of pattern-matching for a side-effect-shaped
call? The injection has to know WHAT to inject (counter.increment vs.
cache.put vs. auditLog.append), and that depends on the sample's
collaborators — there is no universal "side-effect statement" pattern.
A `// LLM06_INJECT: <code>` line in each sample lets the sample author
declare the realistic injection alongside the clean code, which is
both readable and trivially deterministic to apply.

Operation:

    // LLM06_INJECT: viewCounter.increment(req.tenantId());

becomes (after injection):

    viewCounter.increment(req.tenantId());

The leading whitespace before `//` is preserved as the new statement's
indent. All marker lines in the file are processed (samples typically
have one per @Tool method).
"""

from __future__ import annotations

import re

from .base import Injection

_HINT_RE = re.compile(
    r"^(?P<indent>\s*)//\s*LLM06_INJECT:\s*(?P<code>.+?)\s*$",
    re.MULTILINE,
)


class Llm06AddUnannouncedWrite(Injection):
    """Replace `// LLM06_INJECT: <code>` hint lines with `<code>` (preserving indent)."""

    name = "llm06_add_unannounced_write"

    def apply(self, java_source: str) -> str:
        if not _HINT_RE.search(java_source):
            raise ValueError(
                "no `// LLM06_INJECT: <code>` marker found — "
                "this injection is not applicable to the given source"
            )

        def _replace(match: re.Match[str]) -> str:
            return f"{match.group('indent')}{match.group('code')}"

        return _HINT_RE.sub(_replace, java_source)
