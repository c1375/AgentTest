# Pattern: Chain workflow / Prompt assembler

Loaded by `SKILL.md` Step 1 when the target builds prompts from user
input (single-shot prompt assembler) OR iterates LLM calls where each
response cycles into the next prompt (chain workflow). Both surfaces
have the same OWASP LLM01 risk shape; they differ in test structure.

## Pattern recognition signals

**Single-shot prompt assembler** if:
- Method takes a `String` user-input parameter
- Builds a `PromptTemplate` / `Prompt` from it (Spring AI), OR
- Constructs a prompt string via `String.format(...)` / `+` concat /
  `StringBuilder`
- Sends it via `ChatClient.prompt(...)`, `ChatModel.call(...)`, or
  similar single-call API

**Chain workflow** if:
- Iterates over a list of system prompts / steps (`for (String prompt : steps)`)
- Calls LLM in a loop, response from step N becomes input to step N+1
- Often returns the final step's response

If neither signal matches → not a prompt assembler / chain workflow.
**Refuse**: "no prompt-assembler / chain-workflow pattern detected in
this file."

## OWASP risk

LLM01 — Prompt Injection (direct for single-shot, direct + indirect
for chain workflow). See `rules/owasp/llm01-prompt-injection.md` for
the invariant + canonical attack payloads.

## Test structure for single-shot assembler

1 user input variable → 1 `ArgumentCaptor` on the prompt sink:

```java
@Test
void assemble_userInputContainsTemplateBreakout_promptDoesNotLeakPayload() {
    // Given
    ArgumentCaptor<String> promptCaptor = ArgumentCaptor.forClass(String.class);
    when(chatClient.prompt(promptCaptor.capture())).thenReturn(promptSpec);
    when(promptSpec.call()).thenReturn(responseSpec);
    when(responseSpec.content()).thenReturn("any benign response");

    // When
    target.assemble(PAYLOAD_TEMPLATE_BREAKOUT);

    // Then
    assertThat(promptCaptor.getValue())
        .doesNotContain("}}")
        .doesNotContain("Ignore previous")
        .doesNotContain("system:");
}
```

## Test structure for chain workflow (multi-step)

N steps → 1 captor capturing all N invocations via `getAllValues()`.

The KEY insight: the LLM's response in step N becomes input to step
N+1's prompt. If the user payload survives into the response (because
the LLM "complied" with the injection), step N+1's prompt is poisoned
even if step 0's prompt was sanitized. **The test must inspect EVERY
captured prompt.**

```java
@Test
void chain_userInputContainsInstructionOverride_noStepLeaksPayload() {
    // Given
    ArgumentCaptor<String> promptCaptor = ArgumentCaptor.forClass(String.class);
    when(chatClient.prompt(promptCaptor.capture())).thenReturn(promptSpec);
    when(promptSpec.call()).thenReturn(responseSpec);
    // Each step's mock response. Try to simulate the LLM "complying"
    // with the injection by echoing back the override phrase — this
    // is what would happen against a vulnerable LLM.
    when(responseSpec.content())
        .thenReturn(PAYLOAD_PLAIN_OVERRIDE)  // step 0 LLM "complied"
        .thenReturn("benign output 1")
        .thenReturn("benign output 2")
        .thenReturn("final output");

    // When
    target.chain(PAYLOAD_PLAIN_OVERRIDE);

    // Then — every step's prompt must be free of the payload
    List<String> capturedPrompts = promptCaptor.getAllValues();
    assertThat(capturedPrompts).isNotEmpty();
    for (String captured : capturedPrompts) {
        assertThat(captured).doesNotContain("Ignore above");
    }
}
```

## Reference target: ChainWorkflow.java

`spring-projects/spring-ai-examples @ 2a6088d`,
`agentic-patterns/chain-workflow/src/main/java/com/example/agentic/ChainWorkflow.java`,
line 121:

```java
String input = String.format("{%s}\n {%s}", prompt, response);
response = chatClient.prompt(input).call().content();
```

- No `sanitize(...)` step → user input + LLM response cycle into prompts
  verbatim
- Both direct (step 0 with user input) AND indirect (step 1+ with LLM
  response) injection surfaces
- A correct test catches BOTH surfaces with the `getAllValues()` loop
  shown above

This file is the **anchor** for AgentTest's Phase 2 real-world eval —
the skill should produce a test class that flags this exact bug.

## Source

Original to AgentTest. ChainWorkflow.java reference:
<https://github.com/spring-projects/spring-ai-examples/blob/2a6088d/agentic-patterns/chain-workflow/src/main/java/com/example/agentic/ChainWorkflow.java>
