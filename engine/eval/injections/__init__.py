"""Deterministic OWASP risk injections.

Each injection is an `Injection` subclass that takes clean Java source
and returns a buggy variant where one OWASP-class risk is realized.
Injections are deterministic so repeated eval runs over the same sample
produce the same buggy variant.

S2 ships one injection (LLM01). The eval runner (S2 Step 7) will look
up injections by their `name` attribute against this package.
"""

from .base import Injection
from .llm01_remove_sanitization import Llm01RemoveSanitization

__all__ = ["Injection", "Llm01RemoveSanitization"]
