# Rule: Existing-test awareness

## Role in the skill

Before writing a new test class, check the project for existing test
classes. Match conventions (naming, structure, imports, mock patterns).
If a `<TargetClass>Test` or `<TargetClass>Tests` already exists, append
new test methods to it instead of creating a parallel `*AgentGenTest.java`.

## Status

Skeleton — content authoring pending Phase 1.

## Planned content

- Search patterns: `<ClassName>Test.java`, `<ClassName>Tests.java`,
  `<ClassName>AgentGenTest.java`
- If found: read the existing test class, append; do not duplicate
- If not found: scan 2-3 sibling test classes to learn project conventions
  (Junit version, Mockito vs MockK, AssertJ vs Hamcrest, etc.)
- File naming policy: prefer `<Target>AgentGenTest.java` to make
  AgentTest-generated tests reviewable separately

## Source

Original to AgentTest. **`clear-solutions/unit-tests-skills` has no
LICENSE file at time of writing (checked 2026-05-06), so we do NOT
fork its content.** This file's structure (multi-file rules tree)
draws inspiration from common skill conventions; all prose is written
fresh.
