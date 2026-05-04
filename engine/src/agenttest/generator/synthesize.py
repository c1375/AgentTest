"""LLM call + JSON extraction for the test_synthesizer role.

This is the only stage that talks to the LLM in the S2 generation
pipeline. The flow:

  1. Build prompts (`prompt.build_system_prompt`, `build_user_prompt`).
  2. Call `client.complete(...)` and read `response.content[0].text`.
  3. Extract JSON: strict (`json.loads`) → lenient (regex first
     `{...}` block with brace counting + literal-string skipping) →
     retry once with the parser error injected → refuse.
  4. Validate the parsed dict has the expected keys; convert to
     `GeneratedTest`. If the model returns `refused: true`, surface
     that as-is.

See `docs/plan/sprint-2.md` § "Locked decision 7" for why
strict-then-lenient-then-retry-once.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agenttest.agents.client import AgentClient
from agenttest.contracts import GeneratedTest, Grounding, OwaspEntry, OwaspRiskId
from agenttest.generator.prompt import build_system_prompt, build_user_prompt

logger = logging.getLogger(__name__)


class JsonExtractionError(Exception):
    """Raised when neither strict nor lenient JSON parsing succeeded.

    The message lists what was tried so the caller can inject the
    detail back into a retry-prompt. Not a subclass of `ValueError` —
    callers handle this branch specifically.
    """


def _extract_first_json_object(text: str) -> str | None:
    """Return the substring of the first balanced `{...}` block, or None.

    Skips Java/JSON string-literal contents so braces inside strings
    don't fool the depth counter. Handles standard `\\"` escapes.
    """
    depth = 0
    start: int | None = None
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            # Walk the string literal, honoring backslash escapes.
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\":
                    i += 2
                    continue
                i += 1
            i += 1
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                return text[start : i + 1]
        i += 1
    return None


def extract_json(response_text: str) -> dict[str, Any]:
    """Strict-then-lenient JSON extraction.

    1. `json.loads` the whole response.
    2. If that fails, find the first balanced `{...}` block and
       `json.loads` that.
    3. If both fail, raise `JsonExtractionError`.
    """
    text = response_text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError as strict_err:
        block = _extract_first_json_object(text)
        if block is None:
            raise JsonExtractionError(
                f"strict json.loads failed ({strict_err.msg}); "
                "no balanced '{{...}}' block found in response"
            ) from strict_err
        try:
            result = json.loads(block)
        except json.JSONDecodeError as lenient_err:
            raise JsonExtractionError(
                f"strict json.loads failed ({strict_err.msg}); "
                f"lenient json.loads on extracted block also failed "
                f"({lenient_err.msg})"
            ) from lenient_err

    if not isinstance(result, dict):
        raise JsonExtractionError(
            f"parsed JSON is {type(result).__name__}, expected object"
        )
    return result


_REQUIRED_KEYS: tuple[str, ...] = (
    "risk_id",
    "target_lines",
    "test_method_source",
    "assertion_rationale",
)


def _to_generated_test(
    parsed: dict[str, Any],
    grounding: Grounding,
) -> GeneratedTest:
    """Convert a parsed JSON dict to a `GeneratedTest`.

    Surfaces `refused: true` as-is (with the model's `refusal_reason`).
    Otherwise validates the required keys and coerces `target_lines`
    to a `tuple[int, int]`.
    """
    if parsed.get("refused") is True:
        reason = parsed.get("refusal_reason") or "model refused without a reason"
        return GeneratedTest(
            risk_id=grounding.risk_id,
            target_lines=(grounding.site.line_start, grounding.site.line_end),
            test_method_source="",
            assertion_rationale="",
            refused=True,
            refusal_reason=str(reason),
        )

    missing = [k for k in _REQUIRED_KEYS if k not in parsed]
    if missing:
        raise JsonExtractionError(
            f"parsed JSON missing required keys: {missing}"
        )

    raw_lines = parsed["target_lines"]
    if not isinstance(raw_lines, (list, tuple)) or len(raw_lines) != 2:
        raise JsonExtractionError(
            f"target_lines must be a 2-element list, got {raw_lines!r}"
        )
    try:
        line_start, line_end = int(raw_lines[0]), int(raw_lines[1])
    except (TypeError, ValueError) as exc:
        raise JsonExtractionError(f"target_lines values must be ints: {exc}") from exc

    # Coerce the risk_id back to the grounded value: the model is
    # instructed to echo grounding.risk_id verbatim, but we don't trust
    # it. Using grounding.risk_id keeps the (site, risk) traceability
    # honest even if the model hallucinated a different label.
    return GeneratedTest(
        risk_id=grounding.risk_id,
        target_lines=(line_start, line_end),
        test_method_source=str(parsed["test_method_source"]),
        assertion_rationale=str(parsed["assertion_rationale"]),
        refused=False,
        refusal_reason=None,
    )


def _response_text(response: Any) -> str:
    """Pull the text out of the first content block of a Message.

    Anthropic's Messages API returns a list of content blocks; for
    text-only responses the first block has `.text`. We don't try to
    handle tool-use blocks here — the synthesizer prompt asks for a
    plain JSON string, so a tool-use block is itself a contract
    violation.
    """
    content = getattr(response, "content", None)
    if not content:
        raise JsonExtractionError("response has no content blocks")
    first = content[0]
    text = getattr(first, "text", None)
    if text is None:
        raise JsonExtractionError(
            f"response content[0] has no `.text` attribute "
            f"(type={type(first).__name__})"
        )
    return str(text)


async def synthesize(
    grounding: Grounding,
    client: AgentClient,
    owasp_catalog: dict[OwaspRiskId, OwaspEntry],  # noqa: ARG001 — reserved for S3 multi-risk
    target_class_fqn: str,
) -> GeneratedTest:
    """Generate one JUnit 5 test method for `(site, risk_id)`.

    On JSON parse failure, retry once with the parser error injected
    into the user message. On a second failure, return a refused
    `GeneratedTest` so the caller can record the refusal and continue.

    Real `AgentClient.complete` errors (auth, rate limit, network) are
    NOT caught here — they propagate so the caller can decide whether
    to drop the site or abort the run.

    `target_class_fqn` is the fully-qualified name of the class under
    test (e.g., `com.example.spring.RestaurantPromptAssembler`). The
    model uses it verbatim to construct the instance — without it, the
    snippet alone doesn't disambiguate the class name and Sonnet is
    prone to inventing one.
    """
    system = build_system_prompt()
    user_prompt = build_user_prompt(grounding, target_class_fqn)
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]

    response = await client.complete(system=system, messages=messages)
    raw_text = _response_text(response)

    first_err: JsonExtractionError | None = None
    try:
        parsed = extract_json(raw_text)
        return _to_generated_test(parsed, grounding)
    except JsonExtractionError as exc:
        first_err = exc
        logger.info(
            "[generator] JSON parse failed for %s on first try (%s); retrying once",
            grounding.risk_id,
            first_err,
        )

    retry_messages: list[dict[str, Any]] = [
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": raw_text},
        {
            "role": "user",
            "content": (
                f"That response could not be parsed as JSON: {first_err}. "
                "Please return ONLY a single JSON object matching the schema, "
                "no prose, no markdown fences."
            ),
        },
    ]

    retry_response = await client.complete(system=system, messages=retry_messages)
    retry_text = _response_text(retry_response)

    try:
        parsed = extract_json(retry_text)
        return _to_generated_test(parsed, grounding)
    except JsonExtractionError as second_err:
        logger.info(
            "[generator] JSON parse failed for %s on retry (%s); refusing site",
            grounding.risk_id,
            second_err,
        )
        return GeneratedTest(
            risk_id=grounding.risk_id,
            target_lines=(grounding.site.line_start, grounding.site.line_end),
            test_method_source="",
            assertion_rationale="",
            refused=True,
            refusal_reason="JSON parse failure after retry",
        )
