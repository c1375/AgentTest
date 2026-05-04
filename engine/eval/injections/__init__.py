"""Deterministic OWASP risk injections.

Each injection is an `Injection` subclass that takes clean Java source
and returns a buggy variant where one OWASP-class risk is realized.
Injections are deterministic so repeated eval runs over the same sample
produce the same buggy variant.

S2 shipped LLM01. S3 adds LLM06 (un-comment a `// LLM06_INJECT:` hint)
and LLM02 (strip privacy-preserving wrapper calls). The eval runner
looks up injections by their `name` attribute via `INJECTIONS_BY_NAME`.
"""

from .base import Injection
from .llm01_remove_sanitization import Llm01RemoveSanitization
from .llm02_drop_redaction import Llm02DropRedaction
from .llm06_add_unannounced_write import Llm06AddUnannouncedWrite

INJECTIONS_BY_NAME: dict[str, type[Injection]] = {
    Llm01RemoveSanitization.name: Llm01RemoveSanitization,
    Llm02DropRedaction.name: Llm02DropRedaction,
    Llm06AddUnannouncedWrite.name: Llm06AddUnannouncedWrite,
}

__all__ = [
    "INJECTIONS_BY_NAME",
    "Injection",
    "Llm01RemoveSanitization",
    "Llm02DropRedaction",
    "Llm06AddUnannouncedWrite",
]
