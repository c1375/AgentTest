# Pattern: Chain workflow / Prompt assembler

## Role in the skill

Loaded by Step 1 when the target builds prompts from user input
(single-shot prompt assembler) OR iterates LLM calls where each
response cycles into the next prompt (chain workflow). Both surfaces
have the same OWASP LLM01 risk shape; they differ in test structure.

## Status

Skeleton — content authoring pending Phase 1.

## Planned content

- **Pattern recognition signals**:
  - Single-shot assembler: builds a `PromptTemplate` / `Prompt` from
    user input via `Map.of(...)` / string concat
  - Chain workflow: `for (String prompt : steps) { response =
    chatClient.prompt(...).call().content(); }` (response -> next prompt)
- **Test structure for single-shot**:
  - 1 user input variable → 1 ArgumentCaptor on the prompt sink
  - Inject attack payload as input, assert payload not in captured prompt
- **Test structure for chain workflow**:
  - N steps → N ArgumentCaptor invocations (or 1 capturing all calls)
  - Inject attack payload at step 0 (raw user input)
  - Assert payload not in **any** of the N captured prompts (esp. step 1+
    which receives the LLM's response that may re-introduce the payload)
  - This is the **indirect injection** surface — most missed by vanilla
    Claude
- **Reference target**: `ChainWorkflow.java` from spring-ai-examples
  (line 121: `String input = String.format("{%s}\n {%s}", prompt, response);`
  — no sanitization, payload cycles through all 4 steps)

## Source

Original to AgentTest. ChainWorkflow.java reference:
<https://github.com/spring-projects/spring-ai-examples/blob/2a6088d/agentic-patterns/chain-workflow/src/main/java/com/example/agentic/ChainWorkflow.java>
