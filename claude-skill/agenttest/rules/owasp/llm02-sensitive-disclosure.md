# OWASP LLM02 — Sensitive Information Disclosure

> **OWASP mapping**: LLM Top 10 LLM02 (Sensitive Information Disclosure).
> Tangentially related to OWASP Agentic 2026 ASI06 (Memory & Context
> Poisoning) when the leak goes via persistent memory/log sinks that
> influence future agent reasoning.

Loaded by `SKILL.md` Step 1 when target is a log handler, audit-trail
builder, error-response builder, telemetry emitter, or any code that
writes user-attributable data to a sink (log, file, external service).

## The invariant

For any user input X containing **PII** (personally identifiable
information) or secret patterns, the data emitted to the sink (log /
response / audit / telemetry) must NOT contain those patterns
verbatim. Acceptable transformations:

- **Redact**: `***@example.com`, `[REDACTED EMAIL]`, `***-**-6789`
- **Hash**: irreversible one-way (SHA-256 etc.) when used as identifier
- **Truncate**: keep last 4 chars only (typical for credit cards)
- **Drop entirely**: don't log it at all

If the code emits raw user-attributable data with no transformation →
LLM02 risk; the test should catch it.

## Canonical PII / secret attack payloads

```java
// Email (most common PII in Spring AI / chatbot context)
private static final String PAYLOAD_EMAIL = "alice.smith@example.com";

// SSN-like (US format) — also matches similar-shaped identifiers
private static final String PAYLOAD_SSN = "123-45-6789";

// Bearer token (looks like a real OAuth / API token)
private static final String PAYLOAD_BEARER_TOKEN = "Bearer sk-abc123def456ghi789jkl";

// Credit card (Luhn-valid test number — Visa)
private static final String PAYLOAD_CREDIT_CARD = "4111-1111-1111-1111";

// IBAN (EU bank account — UK example)
private static final String PAYLOAD_IBAN = "GB82 WEST 1234 5698 7654 32";

// AWS access key (looks like a real AKIA... key)
private static final String PAYLOAD_AWS_KEY = "AKIAIOSFODNN7EXAMPLE";

// Phone number (international)
private static final String PAYLOAD_PHONE = "+1-555-867-5309";
```

## Assertion approach

Capture the log / response / sink output. Assert no PII payload survives
verbatim.

### Pattern A: Logback `ListAppender` (most reliable)

```java
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import org.slf4j.LoggerFactory;

ListAppender<ILoggingEvent> capturingAppender;
Logger targetLogger;

@BeforeEach
void setupLogCapture() {
    targetLogger = (Logger) LoggerFactory.getLogger(MyService.class);
    capturingAppender = new ListAppender<>();
    capturingAppender.start();
    targetLogger.addAppender(capturingAppender);
}

@AfterEach
void teardownLogCapture() {
    targetLogger.detachAppender(capturingAppender);
}

@Test
void process_userInputContainsEmail_logDoesNotLeakEmail() {
    target.process("Please contact me at " + PAYLOAD_EMAIL);

    String allLogText = capturingAppender.list.stream()
        .map(ILoggingEvent::getFormattedMessage)
        .collect(Collectors.joining("\n"));

    assertThat(allLogText).doesNotContain(PAYLOAD_EMAIL);
}
```

### Pattern B: Spring Boot `OutputCaptureExtension`

```java
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;

@ExtendWith(OutputCaptureExtension.class)
class TargetAgentGenTest {

    @Test
    void process_userInputContainsBearerToken_logDoesNotLeakToken(
            CapturedOutput output) {
        target.process("auth: " + PAYLOAD_BEARER_TOKEN);

        assertThat(output.getOut()).doesNotContain(PAYLOAD_BEARER_TOKEN);
    }
}
```

Pattern A is more precise (captures only the target class's logger).
Pattern B is simpler but captures all stdout/stderr — may match other
log lines unintentionally.

### Pattern C: response-body assertion (for error response leakage)

```java
@Test
void handleError_includesUserEmail_responseRedactsIt() {
    Exception cause = new RuntimeException(
        "Failed to process " + PAYLOAD_EMAIL
    );

    String responseBody = target.handleError(cause);

    assertThat(responseBody).doesNotContain(PAYLOAD_EMAIL);
    // Optional: assert it contains a redacted form
    // assertThat(responseBody).matches(".*\\*\\*\\*@example\\.com.*");
}
```

## What NOT to assert

- ❌ DON'T assert "log message contains the redacted form `***@example.com`"
  — that's testing a specific implementation. The invariant is "raw PII
  not present", not "specific redaction format used".
- ❌ DON'T assert log level / count — irrelevant to LLM02.
- ❌ DON'T mock the logger and verify call count — LLM02 is about output
  content, not call frequency.

## Source

Original to AgentTest. Invariant + payload categories derived from
OWASP LLM Top 10 LLM02 + common PII regex patterns (public material).
