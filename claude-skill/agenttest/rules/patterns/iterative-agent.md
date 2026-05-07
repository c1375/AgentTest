# Pattern: Iterative agent (variable-step LLM loop)

Loaded by `SKILL.md` Step 1 when the target is a **variable-step LLM
loop** — the iteration count or termination condition is determined by
the LLM's output, not by a fixed code constant. Distinct from a chain
workflow.

## Chain workflow vs iterative agent (read this first)

| | Chain workflow | Iterative agent |
|---|---|---|
| Step count | **Fixed** by code (e.g., `for (String p : DEFAULT_SYSTEM_PROMPTS)` — N=4) | **Variable**, controlled by LLM output |
| Termination | Loop ends when array is exhausted | Loop ends when LLM emits final-answer flag, or when external counter hits max |
| Risk surface | LLM01 indirect injection (response → next prompt) | LLM01 + LLM06 (loop runaway, LLM-determined fan-out, sub-agent comm) |
| Test focus | `assertThat(captured).hasSize(N)` exactly | `assertThat(captured).hasSizeLessThanOrEqualTo(MAX)` + bound checks |
| Java target | `ChainWorkflow.java` | `OrchestratorWorkers.java`, `ReflectionAgent.java`, `recursive-advisor-demo` |

**If the file matches both criteria** (e.g., a chain workflow inside a
larger iterative wrapper), prefer iterative-agent rules — they're a
superset.

## Pattern recognition signals

Iterative agent if **any** of:

- LLM output is parsed into a `List` / `Array`, then **for-each loops**
  over that to make more LLM calls (orchestrator-workers pattern)
- Loop body checks `response.isFinalAnswer()` / `response.shouldStop()`
  to break (ReAct / reflection pattern)
- Recursive method that calls itself based on LLM output
  (recursive-advisor-demo)
- Variable `iterations` / `step` / `depth` counter incremented in a
  while-loop with LLM-determined termination

## OWASP risks

- **LLM06 / ASI02** — Tool Misuse (loop runaway, recursion abuse)
- **ASI07** — Insecure Inter-Agent Communication (orchestrator → worker
  prompt isolation)
- **ASI08** — Cascading Agent Failures (one bad LLM output spreads)
- LLM01 / ASI01 — same prompt injection surface as chain workflow
  (load `rules/owasp/llm01-prompt-injection.md` too if applicable)

See `rules/owasp/llm06-excessive-agency.md` for the canonical
invariants. This file focuses on **test patterns**.

## Invariant 1: Bounded total iterations

Even if the LLM never emits a "stop" signal, the loop must terminate
in a bounded number of iterations.

**Test pattern**: mock LLM to **always** emit a continuation signal.

```java
@Test
void agent_llmNeverEmitsFinalAnswer_loopTerminatesWithBound() {
    // Given: ChatClient that always emits a continuation
    when(chatClient.prompt(any(String.class))).thenReturn(promptSpec);
    when(promptSpec.call()).thenReturn(responseSpec);
    when(responseSpec.content()).thenAnswer(invocation ->
        // Always return a tool-call response with no final flag
        "Action: searchDocs\nAction Input: continue"
    );

    // When + Then
    // Option A: agent throws max-iter exception
    assertThatThrownBy(() -> target.run("user task"))
        .hasMessageContaining("max");
    // Option B: agent returns null / fallback after bound
    // String result = target.run("user task");
    // assertThat(result).isNull();  // or whatever fallback contract is

    // Verify the LLM was NOT called more than the documented bound
    verify(chatClient, atMost(MAX_ITERATIONS_DOCUMENTED)).prompt(anyString());
}
```

If the target has **no documented `MAX_ITERATIONS`**, the test should
**fail and report the missing bound** — that's a real bug (ASI08
cascading failure surface).

## Invariant 2: LLM-determined fan-out is capped

Orchestrator-style code where LLM output dictates `tasks.size()` /
worker count must cap that count.

**Test pattern**: mock LLM to return an absurdly large list.

```java
@Test
void orchestrator_llmReturns1000Tasks_workerCountIsCapped() {
    // Given: LLM emits 1000 subtasks (a malicious or runaway response)
    OrchestratorResponse hugeResponse = new OrchestratorResponse(
        "analysis",
        IntStream.range(0, 1000)
            .mapToObj(i -> new SubTask("task " + i, "guidelines"))
            .toList()
    );
    // Mock the full ChatClient fluent chain. Spring AI's structured-output
    // call uses .entity(Class) on the response spec.
    when(chatClient.prompt(anyString())).thenReturn(promptSpec);
    when(promptSpec.call()).thenReturn(responseSpec);
    when(responseSpec.entity(OrchestratorResponse.class))
        .thenReturn(hugeResponse);
    // Worker calls return benign content
    when(responseSpec.content()).thenReturn("worker output");

    // When
    target.execute("user task");

    // Then: worker invocations must be capped, not 1+1000
    verify(chatClient, atMost(REASONABLE_WORKER_CAP + 1))  // +1 for orchestrator
        .prompt(anyString());
}
```

If the orchestrator has no cap (like `OrchestratorWorkers.java` in
spring-ai-examples), this test will FAIL — catching a real ASI02 / ASI08
risk in upstream code.

## Invariant 3: Sub-agent / worker prompt isolation (ASI07)

When the orchestrator's prompt receives malicious input, the worker
prompts (downstream) must not contain the payload verbatim.

**Test pattern**: same as chain-workflow's indirect injection test —
inject payload, capture all prompts, assert payload doesn't survive
into worker prompts.

```java
@Test
void orchestrator_userInputContainsInjection_workerPromptsAreClean() {
    ArgumentCaptor<String> promptCaptor = ArgumentCaptor.forClass(String.class);
    when(chatClient.prompt(promptCaptor.capture())).thenReturn(promptSpec);
    when(promptSpec.call()).thenReturn(responseSpec);
    // ... mock orchestrator to return a benign 2-task response
    // ... mock worker calls return benign

    target.execute(PAYLOAD_TEMPLATE_BREAKOUT);  // see rules/owasp/llm01

    // capturedPrompts[0] = orchestrator prompt
    // capturedPrompts[1..N] = worker prompts
    List<String> all = promptCaptor.getAllValues();
    // The orchestrator prompt naturally contains user input — assertion
    // is on the WORKER prompts (index 1+) which should be derived from
    // the orchestrator's PARSED response, not from raw user input
    for (int i = 1; i < all.size(); i++) {
        assertThat(all.get(i)).doesNotContain("}}");
    }
}
```

## Pitfalls

1. **`thenAnswer(...)` for "always continue"** is the right Mockito
   pattern — `thenReturn(x, y)` runs out and returns last value forever
   (which may not be a continuation signal).
2. **Don't conflate iteration count with prompt count** — orchestrator
   makes 1 prompt call but spawns N worker calls. ArgumentCaptor sees
   1+N prompts.
3. **`@MockitoSettings(strictness = LENIENT)` may be needed** if some
   stubs aren't always exercised across all test methods.

## Source

Original to AgentTest. References:
- OWASP Top 10 for Agentic Applications 2026 (ASI02 / ASI07 / ASI08)
- LangChain `max_iterations` pattern (community convention,
  <https://langchain-doc.readthedocs.io/en/latest/modules/agents/examples/max_iterations.html>)
- spring-ai-examples agentic patterns:
  <https://github.com/spring-projects/spring-ai-examples/tree/main/agentic-patterns>
