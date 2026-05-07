# OWASP LLM06 — Excessive Agency

## Role in the skill

Loaded by Step 1 when the target is a tool handler (`@Tool` annotation,
MCP server tool, function-calling handler).

## Status

Skeleton — content authoring pending Phase 1.

## Planned content

- **Canonical invariant 1 (description-vs-implementation conformance)**:
  the tool's `@Tool(description = "...")` declared behavior must match
  what the implementation actually does. A tool described as "read-only"
  must not execute writes / sends / deletes during its nominal path.
- **Canonical invariant 2 (no unannounced side-effects)**: the tool must
  not invoke side-effects that aren't reflected in its description
  (e.g., logging user query to external service, writing to filesystem,
  making external HTTP calls, mutating shared state).
- **Canonical attack approach**:
  - Mock all I/O dependencies (filesystem, HTTP client, DB, external
    service clients)
  - Invoke the tool with a benign input
  - Assert that mocks for unauthorized side-effect targets are
    `verifyNoInteractions(...)` — ZERO calls
  - Cross-check the tool's `description` string against the side-effects
    it allows
- **Specific anti-patterns to detect**:
  - `@Tool(description = "Read X")` method that calls `Files.write(...)` /
    `restTemplate.post(...)` / `entityManager.persist(...)` etc.
  - MCP tool registration that lies about its capabilities

## Source

OWASP Top 10 for LLM Applications 2025 (LLM06) + OWASP Top 10 for
Agentic AI 2026. **TODO: pin canonical versions + URLs in Phase 1.**
