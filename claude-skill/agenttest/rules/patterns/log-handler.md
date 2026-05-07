# Pattern: Log handler (request / response / audit)

## Role in the skill

Loaded by Step 1 when the target emits user-attributable data to a sink
— logger, audit trail, error response builder, telemetry, monitoring.

## Status

Skeleton — content authoring pending Phase 1.

## Planned content

- **Pattern recognition signals**:
  - `Logger logger = LoggerFactory.getLogger(...)` field + `logger.{info,
    warn, error, debug}(...)` calls referencing method parameters
  - Field type ending in `Logger` / `Log` (JUL, SLF4J, Apache Commons, Logback)
  - Audit-trail builder that includes raw user data
  - Error response that echoes user input back (`return "Failed: " + userInput`)
- **Test structure**:
  - Capture log output via Logback `ListAppender` / Spring Boot
    `OutputCaptureExtension` / custom `TestLogHandler`
  - Inject PII payload as input (email, SSN-like, bearer token, etc. —
    see `rules/owasp/llm02-sensitive-disclosure.md`)
  - Assert captured log does NOT contain the PII substring verbatim
- **Specific anti-patterns**:
  - `logger.info("Processing request: " + req)` where `req.toString()`
    leaks fields
  - `logger.error("User " + userId + " failed auth with token " + token)`
  - `auditTrail.append(rawRequest)` without redaction

## Source

Original to AgentTest.
