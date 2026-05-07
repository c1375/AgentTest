# OWASP LLM02 — Sensitive Information Disclosure

## Role in the skill

Loaded by Step 1 when the target is a log handler (or any code that
emits user-attributable data to a sink — log, error response, audit
trail, telemetry).

## Status

Skeleton — content authoring pending Phase 1.

## Planned content

- **Canonical invariant**: for any user input X containing PII patterns,
  the data emitted to the log / response / sink must NOT contain those
  patterns verbatim — they should be redacted (`***`, `[REDACTED]`),
  hashed, or scrubbed.
- **Canonical PII attack payloads**:
  ```
  email:        "user@example.com"
  SSN-like:     "123-45-6789"
  bearer token: "Bearer sk-abc123def456"
  credit card:  "4111-1111-1111-1111"
  IBAN-ish:     "GB82 WEST 1234 5698 7654 32"
  ```
- **Assertion approach**: capture the log output (e.g., Logback
  `ListAppender`, Spring Boot `OutputCaptureExtension`, custom
  `TestLogHandler`). Assert captured log does NOT contain the PII
  payload substring.

## Source

OWASP Top 10 for LLM Applications 2025 (LLM02). **TODO: pin canonical
version + URL in Phase 1.**
