"""Cheap parse-check for generator output (`validator/parse.py`).

Wraps a single `@Test` method body in a minimal class skeleton and
runs `javalang` on it. This catches obvious garbage (unbalanced
braces, half-formed expressions) in a few milliseconds, before the
slow run-on-clean stage gets invoked.

Returns a `bool` — True means "parses as a valid Java method"; False
means "drop this generation". Diagnostics aren't returned because at
this layer we don't surface them to the user; the validator gate
logs at INFO when a test is dropped.
"""

import logging

import javalang

logger = logging.getLogger(__name__)


_SKELETON = (
    "import org.junit.jupiter.api.Test;\n"
    "import static org.assertj.core.api.Assertions.assertThat;\n"
    "class _Stub {{\n"
    "{body}\n"
    "}}\n"
)


def parse_check(test_method_source: str) -> bool:
    """Return True iff `test_method_source` parses inside a stub class."""
    if not test_method_source.strip():
        logger.info("[validator/parse] empty test method source")
        return False

    skeleton = _SKELETON.format(body=test_method_source)
    try:
        javalang.parse.parse(skeleton)
    except javalang.parser.JavaSyntaxError as exc:
        logger.info("[validator/parse] javalang JavaSyntaxError: %s", exc)
        return False
    except javalang.tokenizer.LexerError as exc:
        logger.info("[validator/parse] javalang LexerError: %s", exc)
        return False
    return True
