"""Deterministic OWASP risk injections.

Each injection is an `Injection` subclass that takes clean Java source
and returns a buggy variant where one OWASP-class risk is realized.
Injections are deterministic so repeated eval runs over the same sample
produce the same buggy variant.

S2 ships one injection (LLM01). The eval runner (S2 Step 7) looks up
injections by their `name` attribute via `INJECTIONS_BY_NAME`.
"""

from .base import Injection
from .llm01_remove_sanitization import Llm01RemoveSanitization

INJECTIONS_BY_NAME: dict[str, type[Injection]] = {
    Llm01RemoveSanitization.name: Llm01RemoveSanitization,
}

__all__ = ["INJECTIONS_BY_NAME", "Injection", "Llm01RemoveSanitization"]
