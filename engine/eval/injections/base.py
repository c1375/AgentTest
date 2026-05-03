"""Base class for OWASP risk injections.

An injection takes clean Java source and returns buggy Java source where
the named OWASP risk is realized. Each injection is deterministic.
"""

from abc import ABC, abstractmethod


class Injection(ABC):
    """Abstract injection: clean Java -> buggy Java.

    Subclasses must:
    - set `name` (a stable string identifier matching the filename)
    - implement `apply`
    """

    name: str = ""

    @abstractmethod
    def apply(self, java_source: str) -> str:
        """Return the buggy variant of `java_source`.

        Raises
        ------
        ValueError
            When this injection is not applicable to the given source
            (e.g., no `sanitize()` helper found for an LLM01 injection).
        """
