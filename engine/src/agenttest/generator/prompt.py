"""System + user prompt assembly for the test_synthesizer role.

The system prompt is static — role, conventions (JUnit 5 + AssertJ, NO
Mockito since it isn't on the runner classpath in S2), the JSON schema
the model must emit, and the refusal license.

The user prompt is per-call; it threads:

  - the OWASP entry's `invariant_to_assert` verbatim (load-bearing —
    the whole point of that field is to be a machine-readable contract;
    paraphrasing it would defeat the purpose)
  - `exemplar_java` + `exemplar_test` as a few-shot pair
  - the target site source under a clearly-tagged `<target_source>` block
  - the candidate `risk_id` and target line range

The output contract: a single JSON object with `risk_id`,
`target_lines`, `test_method_source`, `assertion_rationale`, and
optional `refused` / `refusal_reason`. The synthesize layer parses
this and converts to a `GeneratedTest`.

The generated `test_method_source` must be a method body only
(`@Test void name() { ... }`) — the aggregator wraps surviving
methods into the final class, so individual generations don't need
package / import / class scaffolding.
"""

from agenttest.contracts import Grounding

_SYSTEM_PROMPT = """\
You are a security-focused JUnit 5 test author for Java AI-agent code.

You receive (1) the source of a method that handles user input on a
prompt-assembly path, (2) a labeled OWASP risk and a machine-readable
invariant the test must enforce, and (3) one few-shot example pair
showing a similar violation and the test that catches it.

Your job: emit a single `@Test void <name>() { ... }` method that
fails when the invariant is violated and passes when it is upheld.

CONVENTIONS:
  - JUnit 5 (`org.junit.jupiter.api.Test`) + AssertJ
    (`org.assertj.core.api.Assertions.assertThat`).
  - DO NOT use Mockito — it is not on the runner classpath in S2.
    Construct the target class directly with `new ...()`. Do not emit
    `import org.mockito.*` lines either; the test will fail to compile.
  - **Construct the target class using the EXACT fully-qualified name
    given in `<target_class_fqn>`.** Do NOT invent a class name, do
    NOT shorten the package, do NOT guess the constructor based on
    the snippet. Call the method named in `<target_method_name>` on
    that exact instance.
  - **Only reference Java symbols (classes, methods, fields, inner
    types) that appear verbatim in `<target_source>` or are part of
    the JDK / JUnit 5 / AssertJ / Spring AI / LangChain4j / MCP public
    APIs.** Do NOT invent inner classes, fields, or helper methods on
    the target class. If a symbol you would need is not visible in the
    target source, refuse via the refusal license below rather than
    hallucinating one — a test that references a non-existent symbol
    will fail to compile and be dropped by the validator gate, costing
    a recall opportunity for nothing.
  - Output a SINGLE @Test method body. NOT a full class. The
    aggregator wraps surviving methods into a class.
  - The test must be self-contained: any input fixtures (e.g., the
    malicious payload string) live inside the method.
  - Anchor your assertion to the provided invariant. Do NOT write a
    tautological assertion that always passes (e.g., asserting that
    a string equals itself).
  - Do NOT invent your own PromptTemplate inside the test. The whole
    point of the test is to exercise the target class's behavior on
    adversarial input — rebuilding the template inside the test
    bypasses the very code the test is supposed to check.

OUTPUT FORMAT — return a SINGLE JSON object with these keys, NO prose
before or after, NO markdown fences:

  {
    "risk_id": "<the risk_id you were given, verbatim>",
    "target_lines": [<line_start>, <line_end>],
    "test_method_source": "<a single @Test method, java source>",
    "assertion_rationale": "<one sentence: which invariant clause this test enforces>",
    "refused": false,
    "refusal_reason": null
  }

REFUSAL LICENSE: if you cannot write a meaningful test for the
(site, risk) pair given — e.g., the target method has no observable
output relevant to the invariant — set `"refused": true` and
`"refusal_reason": "<one-sentence reason>"`. Leave the other fields
as empty strings or zeros. Do NOT invent a tautological test just to
satisfy the schema.
"""


def build_system_prompt() -> str:
    """Return the static system prompt for the test_synthesizer role."""
    return _SYSTEM_PROMPT


def build_user_prompt(grounding: Grounding, target_class_fqn: str) -> str:
    """Assemble the per-call user prompt from a `Grounding`.

    The OWASP `invariant_to_assert` is threaded verbatim under an
    `<invariant>` tag. The exemplar pair appears as `<exemplar_java>`
    + `<exemplar_test>`. The target site source appears under
    `<target_source>`. The target class's fully-qualified name appears
    under `<target_class_fqn>` so the model doesn't have to (mis-)infer
    it from the snippet.
    """
    site = grounding.site
    entry = grounding.owasp_entry

    return (
        "Generate ONE JUnit 5 test method that enforces the invariant "
        "below, on the target source below.\n\n"
        f"<risk_id>{grounding.risk_id}</risk_id>\n"
        f"<risk_title>{entry.title}</risk_title>\n\n"
        "<risk_description>\n"
        f"{entry.description.rstrip()}\n"
        "</risk_description>\n\n"
        "<invariant>\n"
        f"{entry.invariant_to_assert.rstrip()}\n"
        "</invariant>\n\n"
        "<exemplar_java>\n"
        f"{entry.exemplar_java.rstrip()}\n"
        "</exemplar_java>\n\n"
        "<exemplar_test>\n"
        f"{entry.exemplar_test.rstrip()}\n"
        "</exemplar_test>\n\n"
        f"<target_class_fqn>{target_class_fqn}</target_class_fqn>\n"
        f"<target_method_name>{site.method_name}</target_method_name>\n"
        f"<target_lines>[{site.line_start}, {site.line_end}]</target_lines>\n\n"
        "<target_source>\n"
        f"{site.snippet.rstrip()}\n"
        "</target_source>\n\n"
        "Return the JSON object now. No prose, no markdown fences."
    )
