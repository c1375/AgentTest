# Pattern: Log handler (request / response / audit)

Loaded by `SKILL.md` Step 1 when the target emits user-attributable
data to a sink (logger, audit-trail builder, error-response builder,
telemetry, monitoring).

## Pattern recognition signals

You're looking at a log handler if **any** of:

- Class has a `Logger` / `Log` field (`LoggerFactory.getLogger(...)`,
  JUL, SLF4J, Apache Commons Logging) AND uses it with method
  parameters as args (`logger.info("...", req)`, `logger.error("user " + userId)`)
- Method builds an audit-trail entry that includes raw user data
- Method builds an error-response body that echoes user input back
  (`return "Failed: " + userInput`)
- Method publishes telemetry / metrics with user data as labels

## OWASP risks

Primary: **LLM02 (Sensitive Information Disclosure)**.

Tangentially: ASI06 (Memory & Context Poisoning) — when the log feeds
back into agent context (e.g., the agent reads its own audit log).

For invariants + canonical PII payloads, see
`rules/owasp/llm02-sensitive-disclosure.md`. That file documents:

- Canonical PII / secret payloads (email, SSN, bearer token, credit
  card, IBAN, AWS key, phone)
- Three log-capture patterns (Logback `ListAppender`, Spring Boot
  `OutputCaptureExtension`, response-body assertion)
- The invariant: raw PII must not survive into the sink

This file (`log-handler.md`) provides the **pattern recognition** and
the test-wiring specifics.

## Test class skeleton for log handlers

```java
@ExtendWith(MockitoExtension.class)
class AgentLoggerAgentGenTest {

    private static final String PAYLOAD_EMAIL = "alice@example.com";
    private static final String PAYLOAD_BEARER = "Bearer sk-abc123";

    private ListAppender<ILoggingEvent> capturingAppender;
    private Logger targetLogger;
    private AgentLogger target;

    @BeforeEach
    void setup() {
        target = new AgentLogger();
        targetLogger = (Logger) LoggerFactory.getLogger(AgentLogger.class);
        capturingAppender = new ListAppender<>();
        capturingAppender.start();
        targetLogger.addAppender(capturingAppender);
    }

    @AfterEach
    void teardown() {
        targetLogger.detachAppender(capturingAppender);
    }

    @Test
    void logRequest_userInputContainsEmail_logDoesNotLeakEmail() {
        // Given
        String userMessage = "My email is " + PAYLOAD_EMAIL + " thanks";

        // When
        target.logRequest(userMessage);

        // Then
        String allLog = capturingAppender.list.stream()
            .map(ILoggingEvent::getFormattedMessage)
            .collect(Collectors.joining("\n"));
        assertThat(allLog).doesNotContain(PAYLOAD_EMAIL);
    }

    @Test
    void logRequest_userInputContainsBearerToken_logDoesNotLeakToken() {
        target.logRequest("auth: " + PAYLOAD_BEARER);

        String allLog = capturingAppender.list.stream()
            .map(ILoggingEvent::getFormattedMessage)
            .collect(Collectors.joining("\n"));
        assertThat(allLog).doesNotContain(PAYLOAD_BEARER);
    }
}
```

## Variants

### Audit-trail builder (no Logger, builds a structured record)

```java
@Test
void buildAuditEntry_userInputContainsEmail_entryDoesNotLeakEmail() {
    AuditEntry entry = target.buildAuditEntry(
        "user request: " + PAYLOAD_EMAIL
    );

    // The audit entry has a serializable form — check both
    assertThat(entry.getRawMessage()).doesNotContain(PAYLOAD_EMAIL);
    assertThat(entry.toJson()).doesNotContain(PAYLOAD_EMAIL);
}
```

### Error-response builder

```java
@Test
void handleException_userInputContainsEmail_errorResponseRedactsIt() {
    ResponseEntity<ErrorResponse> resp = target.handleException(
        new RuntimeException("processing failed for " + PAYLOAD_EMAIL),
        new MockHttpServletRequest()
    );

    assertThat(resp.getBody().getMessage()).doesNotContain(PAYLOAD_EMAIL);
}
```

## Pitfalls

1. **Logback vs JUL**: `ListAppender` is Logback-specific. If the project
   uses java.util.logging directly, use `Handler` instead (rare in
   Spring AI projects — they almost always use Logback via SLF4J).
2. **Async logging**: if the project uses async appenders, log capture
   may need `Awaitility` to wait for messages to arrive.
3. **Log levels filtered out**: ensure the test logger level is
   permissive (`targetLogger.setLevel(Level.ALL)`) so DEBUG/TRACE
   messages aren't dropped.
4. **MDC / structured logging**: if the project uses MDC fields for
   user data, also assert `MDC.get("userEmail") == null` after the call.

## Java targets

No standalone "log handler" example in spring-ai-examples currently —
log calls are scattered through other examples. For Phase 2 testing,
you'd grep for `logger.info(...)` / `log.error(...)` patterns in the
target codebase and apply this rule when found.

## Source

Original to AgentTest.
