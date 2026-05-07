# Rule: Attack-payload assertions (skill's #1 discipline)

## Role in the skill

This is AgentTest's primary differentiator vs vanilla Claude. Tests must
inject **canonical OWASP attack payloads** as input and assert the payload
chars do NOT survive verbatim in the rendered prompt / log output / tool
side-effect. Tests should:

- **FAIL** on a version of the code where the safety mechanism is missing
  or broken (catches the OWASP risk)
- **PASS** on a version of the code where the safety mechanism is intact
  (no false positive)

This is stronger than testing "current behavior" — current behavior may
be buggy. This is testing **what should be true regardless of current
implementation**.

## Status

Skeleton — content authoring pending Phase 1 of S4 v2 plan (see
`docs/plan/sprint-4.md`).

## Planned content

- Concrete contrast: behavior-match test vs attack-payload-assertion test
- The "test should fail on buggy version" framing
- How to use Mockito `ArgumentCaptor` to inspect what gets sent to the LLM
  (the assertion target, vs the function return value)
- When refusal is the right answer (can't formulate a meaningful invariant)

## Source

Original to AgentTest. Influenced by but distinct from
`clear-solutions/unit-tests-skills/rules/general/test-behaviors-not-methods.md`
(which says "test behaviors not implementation methods" — overlapping but
not identical concept).
