# Rule: Attack-payload assertions (skill's #1 discipline)

This file documents the **framing** that distinguishes AgentTest's
generated tests from generic JUnit tests. Read this once at the start
of every `/agenttest` invocation; it shapes the tests written downstream.

## The framing in one sentence

**Tests inject canonical OWASP attack payloads as input and assert
the payload chars do NOT survive verbatim into the LLM-input / log /
side-effect sink.**

This is **NOT** the same as:
- "Test that the function works on normal input" (behavior matching)
- "Test the function returns the expected string" (output matching)
- "Test the LLM responded with X" (testing the mock, not the code)

## Why this framing matters

Vanilla LLMs writing tests default to **happy-path behavior matching**:

```java
// Anti-pattern (vanilla default):
@Test
void chainProcessesInput() {
    String result = workflow.chain("normal input");
    assertNotNull(result);
    verify(chatClient, times(4)).prompt(anyString());
}
```

This test:
- ✅ Compiles
- ✅ Passes on the current (possibly buggy) code
- ❌ **Will also pass on the fixed code**
- ❌ **Catches no bugs** — it just verifies that the function runs

What we want instead:

```java
// AgentTest's discipline:
@Test
void chain_userInputContainsTemplateBreakout_noStepLeaksPayload() {
    ArgumentCaptor<String> promptCaptor = ArgumentCaptor.forClass(String.class);
    when(chatClient.prompt(promptCaptor.capture())).thenReturn(promptSpec);
    when(promptSpec.call()).thenReturn(responseSpec);
    when(responseSpec.content()).thenReturn("step output");

    workflow.chain(PAYLOAD_TEMPLATE_BREAKOUT);  // canonical attack input

    for (String captured : promptCaptor.getAllValues()) {
        assertThat(captured)
            .doesNotContain("}}")
            .doesNotContain("Ignore previous")
            .doesNotContain("system:");
    }
}
```

This test:
- ✅ Compiles
- ✅ **FAILS on the buggy code** (catches the OWASP risk)
- ✅ **PASSES on the fixed code** (no false positive)
- ✅ Verifies what the code passes to the LLM, not the mock's response

## The discipline checklist

When writing each test, verify:

1. **Input is a canonical attack payload** (not "normal input")
   - LLM01: see `rules/owasp/llm01-prompt-injection.md` (5 payloads)
   - LLM02: see `rules/owasp/llm02-sensitive-disclosure.md` (7 payloads)
   - LLM06: see `rules/owasp/llm06-excessive-agency.md` (adversarial args)

2. **Assertion target is what the code SENDS, not what it RETURNS**
   - For LLM01: the prompt sent to ChatClient (use `ArgumentCaptor`)
   - For LLM02: the log / response / sink output (use ListAppender / OutputCaptureExtension)
   - For LLM06: the mocked side-effect dependencies (use `verifyNoInteractions`)

3. **The test would FAIL on a version of the code with the safety
   mechanism removed**
   - If you can't think of a safety mechanism whose absence would make
     this test fail → it's a behavior-match test, rewrite it
   - This is the litmus test for "is this an invariant test"

4. **The test PASSES on a version of the code with proper safety**
   - This is the precision check
   - Tests should be sensitive to bugs but not over-strict

## Refusal license

If you cannot find an attack-payload-style test for this code:

- Maybe the code has no agent-pattern surface (refuse: "no agent pattern")
- Maybe you can't articulate an invariant for the relevant OWASP risk
  (refuse: "OWASP-X invariant unclear for this code")
- Maybe the code is genuinely too simple to need security tests (refuse:
  "no security-relevant invariant for this trivial method")

**A behavior-match test that doesn't catch bugs is worse than no test**
— it gives false confidence. Refuse rather than fabricate.

## Cross-references

- `rules/owasp/llm01-prompt-injection.md` — LLM01 invariant + payloads
- `rules/owasp/llm02-sensitive-disclosure.md` — LLM02 invariant + payloads
- `rules/owasp/llm06-excessive-agency.md` — LLM06 invariants + 5 sub-sections
- `rules/java/chatclient-mocking.md` — ArgumentCaptor recipe for LLM input

## Source

Original to AgentTest. The "test what should be true, not what is true"
framing is widely cited in BDD / property-based testing literature; the
specific application to OWASP attack payloads as input + ArgumentCaptor
on LLM-bound output is AgentTest's contribution.
