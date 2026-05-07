# Rule: JUnit 5 + Mockito + AssertJ template

## Role in the skill

Baseline template + FORBIDDEN annotations for Java unit tests in the
generated test class.

## Status

Skeleton — content authoring pending Phase 1.

## Planned content

- **FORBIDDEN annotations** (don't use unless explicitly required):
  - `@SpringBootTest` — loads full Spring context, slow, autoconfigures
    real `ChatClient` etc. → triggers API key check at context load
  - `@AutoConfigureMockMvc` — same problem
- **Required pattern** (lightweight unit test):
  ```java
  @ExtendWith(MockitoExtension.class)
  class <Target>AgentGenTest {

      @Mock
      private ChatClient chatClient;
      // (other mocks)

      @InjectMocks
      private <Target> target;

      @Test
      void <method>_<state>_<outcome>() {
          // Given
          ...
          // When
          target.method(...);
          // Then
          assertThat(...).isEqualTo(...);
      }
  }
  ```
- **Imports**:
  - `import static org.assertj.core.api.Assertions.*;`
  - `import static org.mockito.Mockito.*;`
  - `import static org.mockito.ArgumentMatchers.*;`
  - `import org.junit.jupiter.api.Test;`
  - `import org.mockito.ArgumentCaptor;`
  - `import org.mockito.Mock;`
  - `import org.mockito.InjectMocks;`
  - `import org.mockito.junit.jupiter.MockitoExtension;`
- **Naming**: test class = `<TargetClass>AgentGenTest` (the `AgentGen`
  marker makes AgentTest output reviewable separately from human-written
  tests in the same project).

## Source

Forked from
[`clear-solutions/unit-tests-skills/rules/tests/java/unit/java-test-template.md`](https://github.com/clear-solutions/unit-tests-skills/blob/main/skills/generate-tests/rules/tests/java/unit/java-test-template.md).
**License attribution pending — verify clear-solutions LICENSE before
landing actual content (Apache 2.0 / MIT / proprietary).**
