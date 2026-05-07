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

Forked from
[`clear-solutions/unit-tests-skills/rules/tests/general/existing-test-awareness.md`](https://github.com/clear-solutions/unit-tests-skills/blob/main/skills/generate-tests/rules/tests/general/existing-test-awareness.md).
**License attribution pending — verify clear-solutions LICENSE before
landing actual content (Apache 2.0 / MIT / proprietary).**
