# Spring AI ChatClient mocking with ArgumentCaptor

The technical recipe for mocking Spring AI's `ChatClient` fluent API in
a way that lets a test inspect the prompt sent to the LLM (vs only the
function's return value). This is AgentTest's #1 technical contribution
on top of generic JUnit testing.

## The Spring AI ChatClient fluent chain

```java
String response = chatClient
    .prompt(input)               // returns ChatClient.ChatClientRequestSpec
    .call()                      // returns ChatClient.CallResponseSpec
    .content();                  // returns String
```

Each step is a separate Mockito mock interaction. The `ArgumentCaptor`
goes on `chatClient.prompt(input)` to grab `input` (the actual prompt
sent to the LLM).

## Mockito setup pattern

```java
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.ai.chat.client.ChatClient;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TargetAgentGenTest {

    @Mock private ChatClient chatClient;
    @Mock private ChatClient.ChatClientRequestSpec promptSpec;
    @Mock private ChatClient.CallResponseSpec responseSpec;

    private Target target;

    @BeforeEach
    void setup() {
        target = new Target(chatClient);
    }

    @Test
    void someTest() {
        // Capture the prompt argument
        ArgumentCaptor<String> promptCaptor = ArgumentCaptor.forClass(String.class);

        // Wire the fluent chain
        when(chatClient.prompt(promptCaptor.capture())).thenReturn(promptSpec);
        when(promptSpec.call()).thenReturn(responseSpec);
        when(responseSpec.content()).thenReturn("mock response");

        // Trigger the code under test
        target.method("user input");

        // Inspect the captured prompt
        String capturedPrompt = promptCaptor.getValue();
        assertThat(capturedPrompt).contains("user input");
    }
}
```

Note: the `Target` class is constructed manually in `@BeforeEach`
rather than via `@InjectMocks`. `@InjectMocks` works for simple cases
but can be confusing when the target's constructor takes a
`ChatClient.Builder` (some Spring AI samples) — manual construction is
clearer.

## Inspecting captured prompts (multi-step / chain workflow)

Chain workflows call `chatClient.prompt(...)` N times in a loop.
ArgumentCaptor captures all of them:

```java
List<String> capturedPrompts = promptCaptor.getAllValues();
// Step 0 prompt = capturedPrompts.get(0)
// Step 1 prompt = capturedPrompts.get(1)  // received step-0's LLM output as input
// ...
```

For OWASP LLM01 attack-payload assertions, iterate through all captured
prompts and assert the payload doesn't appear in any:

```java
for (String captured : capturedPrompts) {
    assertThat(captured).doesNotContain("}}");
}
```

## Variants

### Builder pattern

Most spring-ai-examples inject `ChatClient.Builder` (not `ChatClient`)
and call `.build()` after configuring defaults like `.defaultSystem(...)`,
`.defaultAdvisors(...)`. To stub the whole fluent chain at once, use
Mockito's `Answers.RETURNS_SELF`:

```java
import org.mockito.Answers;

@Mock(answer = Answers.RETURNS_SELF)
private ChatClient.Builder chatClientBuilder;

@Mock private ChatClient chatClient;

@BeforeEach
void setup() {
    // RETURNS_SELF makes every chained method on the builder return the
    // builder itself, so .defaultSystem(x).defaultAdvisors(y) etc. work
    // without explicit stubs. Override only .build():
    when(chatClientBuilder.build()).thenReturn(chatClient);
    target = new Target(chatClientBuilder);
}
```

If the target only calls `chatClientBuilder.build()` (no fluent
configuration in between), the simpler form works:

```java
@Mock private ChatClient.Builder chatClientBuilder;
@BeforeEach
void setup() {
    when(chatClientBuilder.build()).thenReturn(chatClient);
    target = new Target(chatClientBuilder);
}
```

Pick based on what the target actually calls on the builder.

### Streaming responses

`.stream().content()` returns `Flux<String>`:

```java
import reactor.core.publisher.Flux;

@Mock private ChatClient.StreamResponseSpec streamSpec;

when(promptSpec.stream()).thenReturn(streamSpec);
when(streamSpec.content()).thenReturn(Flux.just("chunk 1", "chunk 2"));
```

### Method invocation with options

`.prompt(...).options(opts).call()` adds an interaction in between:

```java
@Mock private ChatClient.ChatClientRequestSpec promptSpecWithOptions;

when(promptSpec.options(any())).thenReturn(promptSpecWithOptions);
when(promptSpecWithOptions.call()).thenReturn(responseSpec);
```

## Common pitfalls

1. **Forgetting to mock the entire chain** — if `responseSpec.content()`
   isn't stubbed, it returns null, and the code under test may NPE
   before reaching the assertion. Always mock all 3 levels.
2. **Using `any()` instead of `ArgumentCaptor.capture()`** — `any()`
   matches but doesn't record. Use the captor for prompt inspection.
3. **One captor for N invocations** — `getValue()` returns the LAST
   captured value, `getAllValues()` returns all. Use `getAllValues()`
   for chain workflows.
4. **Strict stubbing failures** — Mockito 5+ enforces strict stubbing.
   If you see `UnnecessaryStubbingException`, remove unused mocks or
   use `@MockitoSettings(strictness = Strictness.LENIENT)` (sparingly).
5. **Generic type erasure** — `ArgumentCaptor<String>` works fine via
   `ArgumentCaptor.forClass(String.class)`. Avoid `ArgumentCaptor.captor()`
   (Mockito 5 method) on Java versions where it's not available.

## Source

Original to AgentTest. Spring AI ChatClient API reference:
<https://docs.spring.io/spring-ai/reference/1.0/api/chatclient.html>

This recipe (multi-level mock + ArgumentCaptor on `prompt()`) is the
file that doesn't exist in `clear-solutions/unit-tests-skills` — one of
AgentTest's primary technical contributions.
