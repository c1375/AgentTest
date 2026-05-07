---
name: agenttest
description: Generate JUnit 5 tests for Java AI agent code (Spring AI / LangChain4j / MCP) using canonical OWASP LLM Top 10 attack payloads. Tests fail on the OWASP risk and pass on correct code. Outputs are advisory — human review required before merge.
disable-model-invocation: true
allowed-tools: Read Bash Write Glob Grep
---

# /agenttest <file>

Generate a JUnit 5 test class for `$ARGUMENTS` that catches OWASP LLM
Top 10 risks in Java AI agent code (Spring AI / LangChain4j / MCP idiom).

## Prerequisites (refuse early if any missing)

- Target file is Java AI agent code matching one of the patterns below
- Project uses Maven (skill shells out to `mvn test-compile` / `mvn test`)
- JDK 17+ on PATH
- Test will land in a Maven project with `spring-boot-starter-test` (for JUnit 5
  + Mockito + AssertJ) or equivalent on the test classpath

If a prerequisite fails, say so explicitly and stop. Don't fabricate.

## Workflow

### Step 1: Read target + identify agent pattern

Use the Read tool on `$ARGUMENTS`. Classify the agent pattern:

| Pattern | Signal | Load these rule files |
|---|---|---|
| chain workflow / prompt assembler | iterates LLM calls (response cycles into next prompt) OR builds prompt from user input | `rules/patterns/chain-workflow.md` + `rules/owasp/llm01-prompt-injection.md` |
| tool handler / MCP server | `@Tool` annotation, MCP server tool registration, function calling | `rules/patterns/tool-handler.md` + `rules/owasp/llm06-excessive-agency.md` |
| log handler | logs request / response / user-attributable data | `rules/patterns/log-handler.md` + `rules/owasp/llm02-sensitive-disclosure.md` |

If the file fits none of the above → **refuse**: "no agent pattern detected
in this file; AgentTest does not apply."

### Step 2: Read general discipline rules

Always read:
- `rules/general/attack-payload-assertions.md` — assertion discipline (the
  skill's #1 differentiator: tests assert that canonical OWASP payloads
  do NOT survive in the rendered prompt / log / tool side-effect)
- `rules/general/existing-test-awareness.md` — match project conventions

### Step 3: Plan test cases (BEFORE writing code)

Output a Given-When-Then table:

```
| # | Test name | Given | When | Then |
|---|---|---|---|---|
| 1 | <method>_<state>_<outcome> | ... | ... | ... |
```

Test name format: `{methodName}_{givenState}_{expectedOutcome}`.
Example: `chain_userInputContainsTemplateBreakout_promptDoesNotLeakPayload`.

### Step 4: Ask user to confirm

Use the **AskUserQuestion** tool (Claude Code ≥ 2.0.21):
- Question: "Test cases above. Generate test code?"
- Options:
  - "Yes, generate" — proceed to Step 5
  - "No, let me adjust first" — stop and wait

If `AskUserQuestion` is unavailable (older Claude Code), print the prompt
and wait for explicit user reply.

### Step 5: Generate test code

Read the Java rules:
- `rules/java/junit-template.md` — JUnit 5 + Mockito + AssertJ template,
  FORBIDDEN annotations (e.g., `@SpringBootTest` for unit tests)
- `rules/java/chatclient-mocking.md` — Spring AI `ChatClient` fluent API
  mocking with `ArgumentCaptor` (the trick that lets a test inspect the
  prompt sent to the LLM)

Write the test class. Hard constraints:
- Class name: `<TargetClass>AgentGenTest`
- Package: matches target's package (so the test can `new <TargetClass>()`
  without an import)
- ONLY reference symbols visible in the target source — do NOT invent
  inner classes, fields, or helper methods on the target
- Use Mockito for DI'd interfaces (`ChatClient`, etc.)
- Use canonical OWASP attack payloads from the `rules/owasp/` file loaded
  in Step 1

### Step 6: Verify

Read `rules/post-generation/verify.md`. Run from the project root:

1. **Compile preflight**: `mvn test-compile -q`
   - On failure: read the diagnostic, fix imports / types, retry. Max 5 attempts.
   - If still failing after 5: deliver test source with a warning.

2. **Run on current target**: `mvn test -Dtest=<TargetClass>AgentGenTest -q`
   - Record per-method outcome (PASS / FAIL / ERROR)
   - This is the V_buggy run if the target has the OWASP risk

3. **Run on V_clean (if user provides one)**: same command after the user
   swaps in the fixed version. Tests should PASS on V_clean.
   - Max 3 attempts to fix tests that fail on V_clean (assertion was too
     strict). **Never modify production code to make tests pass.**

### Step 7: Output

Print to the conversation:
- The test class source (full, not just diff)
- The Given-When-Then test case table from Step 3
- The verification report from Step 6 (which methods PASS / FAIL on which version)

**Do NOT write to `src/test/java/` without explicit user confirmation.**
Generated tests are advisory; user reviews before merge (CLAUDE.md rule 2).

## Refusal license

If at any step you can't proceed honestly:
- Target not Java AI agent code → refuse
- Pattern unclear / multiple ambiguous → refuse, list candidates
- Can't formulate an OWASP-relevant test → refuse
- Project not Maven → refuse, point to limitation
- mvn fails after retry budget → deliver source + warning

A test that asserts current buggy behavior is worse than no test.

## Related work (don't claim novelty)

OWASP audit / review skills exist:
- [`agamm/claude-code-owasp`](https://github.com/agamm/claude-code-owasp) — OWASP best practices across many languages
- [`AgriciDaniel/claude-cybersecurity`](https://github.com/AgriciDaniel/claude-cybersecurity) — comprehensive cybersec code review

AgentTest fills the adjacent niche: **JUnit test generation** scoped to
**Java AI agent code**, with **canonical OWASP attack payload assertions**
as the differentiator vs vanilla Claude.

Structural reference for the skill organization:
[`clear-solutions/unit-tests-skills`](https://github.com/clear-solutions/unit-tests-skills) —
general Java JUnit test generation skill. AgentTest's `rules/general/` and
`rules/java/junit-template.md` borrow from this structure (license TBD;
proper attribution in those files).
