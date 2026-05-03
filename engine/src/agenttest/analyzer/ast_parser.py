"""Java AST parser interface and the default `javalang` implementation.

The Protocol exists so we can swap to a JavaParser-via-subprocess backend
later (architecture decision 2) without touching the analyzer rules.
"""

from typing import Protocol

import javalang
from javalang.tree import CompilationUnit


class JavaAstParser(Protocol):
    """Parses Java source into a `javalang` CompilationUnit."""

    def parse(self, java_source: str) -> CompilationUnit:
        ...


class JavalangParser:
    """Default `JavaAstParser` backed by the pure-Python `javalang` library."""

    def parse(self, java_source: str) -> CompilationUnit:
        return javalang.parse.parse(java_source)
