# Rule: Spring AI ChatClient mocking with ArgumentCaptor

## Role in the skill

Provides the **technical recipe** for mocking Spring AI's `ChatClient`
fluent API in a way that lets a test **inspect the prompt** sent to the
LLM (vs only the function's return value). This is the trick that makes
attack-payload-assertion tests work for LLM01 prompt injection.

## Status

Skeleton — content authoring pending Phase 1.

## Planned content

- **The Spring AI ChatClient fluent chain**:
  ```java
  String response = chatClient
      .prompt(input)               // returns ChatClient.PromptSpec
      .call()                      // returns ChatClient.ResponseSpec
      .content();                  // returns String
  ```
  Each step is a separate Mockito mock interaction; the captor goes on
  `prompt(input)` to grab `input`.
- **Mockito setup pattern**:
  ```java
  ChatClient chatClient = mock(ChatClient.class);
  ChatClient.PromptSpec promptSpec = mock(ChatClient.PromptSpec.class);
  ChatClient.ResponseSpec responseSpec = mock(ChatClient.ResponseSpec.class);

  ArgumentCaptor<String> promptCaptor = ArgumentCaptor.forClass(String.class);
  when(chatClient.prompt(promptCaptor.capture())).thenReturn(promptSpec);
  when(promptSpec.call()).thenReturn(responseSpec);
  when(responseSpec.content()).thenReturn("step 1 output", "step 2 output", "...");
  ```
- **Inspecting captured prompts**:
  ```java
  // After the chain workflow runs:
  List<String> capturedPrompts = promptCaptor.getAllValues();
  // Step 0 prompt = capturedPrompts.get(0)
  // Step 1 prompt = capturedPrompts.get(1)  (received step-0's LLM output as input)
  // ...

  // Assert payload didn't survive into step 0 (direct injection):
  assertThat(capturedPrompts.get(0)).doesNotContain("}}");
  // Assert payload didn't survive into step 1 (indirect via response cycling):
  assertThat(capturedPrompts.get(1)).doesNotContain("system:");
  ```
- **Variants**:
  - Builder pattern: `ChatClient.Builder` is a separate mock target
  - Streaming: `.stream().content()` returns `Flux<String>`
  - With options: `.prompt(...).options(opts).call()` adds an interaction

## Source

Original to AgentTest. Spring AI ChatClient API reference:
<https://docs.spring.io/spring-ai/reference/1.0/api/chatclient.html>

This is the file that doesn't exist in clear-solutions/unit-tests-skills
(which is general Java testing, not Spring AI specific) — one of
AgentTest's primary technical contributions.
