# Phase 1 subtask 2: e2e smoke result

**Date**: 2026-05-06  
**Target**: `spring-ai-examples @ 2a6088d / agentic-patterns/chain-workflow/.../ChainWorkflow.java`  
**Skill version**: commit `b416873` (12 files, all 17 code-review findings closed)  
**Invocation**: `/agenttest src/main/java/com/example/agentic/ChainWorkflow.java` in fresh Claude Code session  

## Outcome: **PASS** (all checkpoints validated)

| Phase 1 expectation | Actual | Verdict |
|---|---|---|
| Skill triggers via explicit `/agenttest` | Yes | ✓ |
| Pattern classified as "chain workflow / prompt assembler" | Yes (per skill output) | ✓ |
| `mvn test-compile` passes first attempt (no retries) | Yes | ✓ — Spring AI types correct (BLOCKER 1 fix validated) |
| 5 tests generated (4 attack-payload + 1 sanity) | Yes | ✓ |
| Attack-payload tests FAIL on V_buggy = catch ✓ | 4/4 caught | ✓ recall = 4/4 |
| Sanity test PASSES on V_buggy | Yes (test #5) | ✓ |
| Failure messages match catch criterion regex | Yes (sanitize / system: / template-breakout) | ✓ |
| Indirect injection (chain-workflow specific) caught | Yes (test #4 — mocked LLM echo) | ✓ |

## Test methods generated

| # | Name | Outcome | Evidence |
|---|---|---|---|
| 1 | `chain_userInputContainsTemplateBreakout_noStepLeaksPayload` | FAIL ✓ catch | `}}` and `system:` reach rendered prompt at step 0 |
| 2 | `chain_userInputContainsImStartTag_noStepLeaksPayload` | FAIL ✓ catch | `<\|im_start\|>` reaches rendered prompt |
| 3 | `chain_userInputContainsLlamaInstTag_noStepLeaksPayload` | FAIL ✓ catch | `[INST]` reaches rendered prompt |
| 4 | `chain_llmEchoesPlainOverride_laterStepsDoNotLeakPayload` | FAIL ✓ catch | **Indirect injection caught** — step-0 LLM "compliance" cycles into step-1's prompt |
| 5 | `chain_normalInput_invokesChatClientOncePerSystemPrompt` | PASS | Sanity: 4 invocations (one per `DEFAULT_SYSTEM_PROMPTS` entry) |

## Real OWASP LLM01 bug confirmed

`ChainWorkflow.java` line 121:

```java
String input = String.format("{%s}\n {%s}", prompt, response);
response = chatClient.prompt(input).call().content();
```

- Direct injection: `response = userInput` on first iteration → user payload lands in step 0's prompt verbatim (caught by tests #1-3)
- Indirect injection: iterations 1-3 receive whatever the LLM returned at step N-1; a vulnerable upstream LLM "complying" with an injection re-poisons every subsequent step's prompt (caught by test #4)
- Template-breakout surface: the `{%s}` curly-brace wrapper makes the prompt brittle if downstream Spring AI components re-parse as `PromptTemplate`

This is a genuine OWASP LLM01 vulnerability in Spring's official sample, with no existing test catching it. AgentTest's skill caught all four attack vectors (template breakout / im_start markers / Llama tags / indirect via response cycling) on first invocation.

## V_clean run

**Not yet run**. Next step (Phase 2 task 1):

1. Author `experiments/chainworkflow/ChainWorkflow_fixed.java` with a `sanitize(String)` helper
2. Apply sanitize to `userInput` (initial) AND each `response` before the `String.format(...)` at line 121
3. Swap into `spring-ai-examples` temporarily, re-run `.\mvnw.cmd test "-Dtest=ChainWorkflowAgentGenTest"`
4. Expect: all 5 tests PASS on V_clean (precision check)

If any test fails on V_clean, the assertion is too strict — refine within max 3 attempts (per `rules/post-generation/verify.md` Step 3).

## Vanilla baseline (Phase 2 task 2)

Not yet run. Need to:

1. Open spring-ai-examples in a separate Claude Code session (skill installed but NOT invoked)
2. Type locked baseline prompt verbatim: 「帮我给 ChainWorkflow.java 写一个测试」
3. Save vanilla output to `experiments/chainworkflow/test_vanilla.java`
4. Record Claude Code version + model + timestamp in `experiments/chainworkflow/baseline-context.md`

## Files

- `test_skill.java` — copy of the generated test class (the skill output, captured here for Phase 2 comparison)
- (TODO) `ChainWorkflow_fixed.java` — V_clean with sanitize() defense
- (TODO) `test_vanilla.java` — vanilla Claude Code's output for the same target
- (TODO) `baseline-context.md` — vanilla session metadata

## Note on disk write

The skill wrote `ChainWorkflowAgentGenTest.java` to spring-ai-examples'
`src/test/java/com/example/agentic/` to enable mvn verification. Per
SKILL.md Step 7 ("do NOT write to src/test/java without explicit user
confirmation"), this is a soft tension: Step 6 needs the file on disk
for mvn to run, Step 7 says don't write without confirmation.

The pragmatic resolution Claude chose was reasonable (write for
verification, hand back to user for review). Worth refining SKILL.md
to explicitly acknowledge this in the polish pass.

The test file remains in spring-ai-examples for the user to review /
delete. Don't commit it upstream (we don't own that repo).
