# Vanilla baseline context (Phase 2 task 2)

## Locked baseline prompt (verbatim)

```
帮我给 ChainWorkflow.java 写一个测试
```

## Session metadata

| Field | Value |
|---|---|
| Date | 2026-05-06 |
| Session cwd | `E:\桌面\Generative AI\spring-ai-examples\agentic-patterns\chain-workflow` |
| Skill installed at session start | Yes (user-level, but NOT invoked) |
| `/agenttest` invocation | NO — vanilla path, plain prompt only |
| Output file | `src/test/java/com/example/agentic/ChainWorkflowTest.java` |
| Output filename convention | `*Test.java` (vanilla default), NOT `*AgentGenTest.java` (skill convention) |
| Test count | 5 |

## What vanilla wrote (5 test methods)

1. `chainReturnsFinalStepResponse` — `assertThat(result).isEqualTo("step4")`
2. `chainInvokesChatClientOncePerSystemPrompt` — `verify(chatClient, times(prompts.length)).prompt(anyString())`
3. `chainFeedsPreviousResponseIntoNextStep` — `assertThat(calls.get(0)).isEqualTo("{PROMPT_A}\n {USER_INPUT}")`
4. `chainWithCustomPromptsUsesProvidedSteps` — config-array test
5. `chainWithEmptyPromptsReturnsInputUnchanged` — empty-prompts edge case

All 5 are **behavior-match tests**: they assert what the current code
does, not what the code SHOULD do regardless of current state.

Notably, test #3 USES `ArgumentCaptor.getAllValues()` (the same Mockito
recipe the skill uses) — but asserts the EXACT current format
`{PROMPT_A}\n {USER_INPUT}` rather than asserting "no attack payload
chars survive". Same tool, opposite framing.

## Vanilla's mock setup style

- Manual `mock(...)` calls in `@BeforeEach` (no `@Mock` annotation,
  no `@ExtendWith(MockitoExtension.class)`)
- Variable names match Spring AI types: `requestSpec`,
  `callResponseSpec`
- Imports `ChatClient.CallResponseSpec` and
  `ChatClient.ChatClientRequestSpec` directly (correct Spring AI 1.0
  type names — confirms vanilla Claude knows the real API)

This validates that the skill's Spring AI ChatClient typing fix
(BLOCKER 1 in code-review pass) was correct: the actual nested types
ARE `ChatClientRequestSpec` / `CallResponseSpec`.

## Empirical mvn test results

### V_buggy (upstream ChainWorkflow.java with LLM01 bug at line 121)

```
Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

All 5 tests PASS on V_buggy → **catch = 0** (vanilla detected nothing
about the LLM01 vulnerability). Tests asserted current behavior;
current behavior IS the bug, so tests trivially pass.

### V_clean (`ChainWorkflow_fixed.java` with sanitize() helper)

```
Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

All 5 tests PASS on V_clean → **precision = ✓** (no false positives).

This was unexpected on my part: I predicted test #3
(`isEqualTo("{PROMPT_A}\n {USER_INPUT}")`) might break under V_clean
because sanitize strips `{`/`}`. But the assertion's `{` and `}` come
from the format wrapper `"{%s}\n {%s}"` (literals in the format
string), not from input — sanitize only affects the `userInput` /
`response` variables. Vanilla used benign input strings ("USER_INPUT",
"first-out") with no payload chars, so sanitize is a no-op for them.
Format produces identical output on V_buggy and V_clean for vanilla's
inputs.

So vanilla has precision intact. The differentiator is purely the
**catch** dimension.

## Verdict

| Mode | Catch | Precision | Headline |
|---|---|---|---|
| skill | ✓ (4/5 fail on V_buggy) | ✓ (5/5 pass on V_clean) | **TRUE** |
| vanilla | ✗ (0/5 fail on V_buggy) | ✓ (5/5 pass on V_clean) | **FALSE** |

Skill wins on catch — the only dimension where the skill's discipline
materially differs from vanilla's defaults. Vanilla matches on
precision (both produce well-formed tests that don't false-positive).

The take-away: **vanilla Claude in Claude Code has the technical
ability to write attack-payload-assertion tests** (it correctly used
ArgumentCaptor.getAllValues, knew Spring AI types) — but doesn't
default to thinking adversarially without explicit framing. The
skill's value-add is the framing + canonical attack payloads, not
new technical knowledge.
