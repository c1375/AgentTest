"""Single-prompt baseline test synthesis.

Calls the BASELINE Claude role with one prompt — no analyzer, no
retrieval, no per-risk loop, no validator gate. Returns the raw Java
test class (extracted from a markdown fence if present) plus a flag
indicating whether the output parses as Java.

The base prompt is verbatim from `docs/project_plan.md` § 4 with three
empirical adjustments documented in `docs/plan/sprint-3.md` § "Step 0":

  - "no Mockito" constraint (Step 0 saw the model emit Mockito
    imports, which would COMPILE_FAIL on the runner-helper classpath
    and unfairly tank baseline recall).
  - target package hint (so the test class lands in the same package
    as the target and can construct it without an import).
  - markdown-fence extraction (Step 0 saw the model wrap output in
    ```java ... ``` after a markdown header).

Why only a parse check (not full validator):

  Pipeline-mode generation goes through validator (compile +
  run-on-clean) which DROPS failing tests, then aggregates survivors.
  Baseline is single-shot: a validator drop would mean "0 tests
  emitted", indistinguishable from "model refused" in eval math. We
  therefore parse-check here (cheap, catches obvious refusals /
  hallucinated prose) and let the eval runner separately track
  compile / run-on-clean outcomes for baseline so the comparison
  surfaces "baseline emits N% un-compilable tests" as its own signal
  rather than burying it in recall numbers.
"""

from __future__ import annotations

import logging
import re

import javalang

from agenttest.agents.client import AgentClient
from agenttest.contracts import BaselineEmission

logger = logging.getLogger(__name__)


_FENCE_RE = re.compile(r"```(?:java)?\s*(.*?)```", re.DOTALL)


BASELINE_PROMPT_TEMPLATE: str = (
    "You are a security-focused Java test engineer. Given the following "
    "Java class implementing AI-agent logic, generate JUnit 5 tests "
    "targeting common OWASP risks for LLM agents (prompt injection, "
    "sensitive-data disclosure, excessive agency / tool description "
    "mismatch, etc.). Output one Java test class file.\n\n"
    "Constraints:\n"
    "  - Use JUnit 5 (org.junit.jupiter.api.Test) and AssertJ "
    "(org.assertj.core.api.Assertions.assertThat).\n"
    "  - DO NOT import or use Mockito (org.mockito.*). The test "
    "classpath does not include Mockito; using it will fail to "
    "compile.\n"
    "  - Place the test class in the package `{target_package}` so it "
    "can construct {target_class_name} without an explicit import.\n"
    "  - The test class name must be `{target_class_name}AgentGenTest`.\n"
    "  - Output only the Java source, optionally wrapped in a single "
    "```java ... ``` block. No prose before or after.\n\n"
    "Target class:\n\n"
    "```java\n{src}\n```"
)


def _extract_java(model_output: str) -> str:
    """Pull Java source out of markdown fences if present.

    If one or more ``` ``` fences are present, return the contents of
    the *longest* one (the one most likely to contain the actual class
    rather than a snippet from the model's preamble). If no fence is
    present, treat the whole output as Java.
    """
    matches = _FENCE_RE.findall(model_output)
    if matches:
        return max(matches, key=len).strip()
    return model_output.strip()


def _response_text(response: object) -> str:
    """Concatenate every text content block in an Anthropic Message.

    Concatenation (vs. taking just `content[0].text` like the
    structured generator does) is intentional: the baseline output
    is one Java class, not one JSON object — if the model splits
    its response into multiple text blocks (e.g., a leading
    rationale block followed by the code block), we want the whole
    thing so the fence extractor sees everything.
    """
    content = getattr(response, "content", None) or []
    parts: list[str] = []
    for block in content:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", None)
            if text:
                parts.append(str(text))
    return "".join(parts)


async def synthesize_baseline(
    java_source: str,
    target_class_name: str,
    target_package: str,
    client: AgentClient,
) -> BaselineEmission:
    """Run the single-prompt baseline against `java_source`.

    Returns a `BaselineEmission` with `java_source` set to the
    extracted Java (after fence stripping) and `parseable` reflecting
    whether `javalang.parse` succeeded on that text. Real
    `AgentClient.complete` errors (auth, rate limit, network) are NOT
    caught here — they propagate so the caller can decide whether to
    drop the sample or abort the run.
    """
    user_msg = BASELINE_PROMPT_TEMPLATE.format(
        src=java_source,
        target_package=target_package,
        target_class_name=target_class_name,
    )

    response = await client.complete(
        messages=[{"role": "user", "content": user_msg}],
    )
    raw_text = _response_text(response)
    extracted = _extract_java(raw_text)

    parseable = True
    try:
        javalang.parse.parse(extracted)
    except (javalang.parser.JavaSyntaxError, javalang.tokenizer.LexerError) as exc:
        logger.info(
            "[baseline] javalang parse failed for %s: %s",
            target_class_name,
            exc,
        )
        parseable = False

    return BaselineEmission(
        target_class_name=target_class_name,
        java_source=extracted,
        parseable=parseable,
    )
