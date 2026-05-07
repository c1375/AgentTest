# Rule: Post-generation verification (compile + execute)

## Role in the skill

Runs after the test code is generated. Mechanically verifies the test
compiles and that the test's expected outcomes hold. Never deliver tests
that don't compile.

## Status

Skeleton — content authoring pending Phase 1.

## Planned content

### Step 6.1: Compile preflight

```bash
mvn test-compile -q 2>&1 | tail -30
```

- **Success**: stdout / stderr empty + exit 0 → continue to 6.2
- **Failure**: parse diagnostics, fix in test source. Common issues:
  - missing imports (look for `cannot find symbol` → add `import ...`)
  - type mismatch in mock setup (e.g., wrong generic, wrong captor type)
  - referenced symbol doesn't exist on target (hallucinated method/field)
  - Mockito version mismatch (rare — usually fine on `spring-boot-starter-test`)
- **Max 5 attempts**. If still failing, deliver source + warning, do not
  insist.

### Step 6.2: Run on current target

```bash
mvn test -Dtest=<TargetClass>AgentGenTest -q 2>&1 | tail -50
```

- Record per-method outcome (PASS / FAIL / ERROR)
- The current target may be V_buggy (has the OWASP risk) — in that case
  attack-payload-assertion tests SHOULD fail (catch ✓)
- Report outcomes back to the user

### Step 6.3: Run on V_clean (if user provides one)

If the user has a fixed version of the target file:
- User swaps in V_clean
- Re-run `mvn test -Dtest=<TargetClass>AgentGenTest -q`
- Tests should PASS on V_clean (no false positives)
- If any test FAILs on V_clean → the assertion is too strict. Inspect,
  refine the test (NEVER modify production code). Max 3 retry attempts.
- If still failing after 3 attempts: drop that test method, report.

### Build system support

This skill assumes Maven. **Gradle / other build systems not yet supported**
— refuse early in Step 1 if `pom.xml` is not present in project root.

## Source

Original to AgentTest. **`clear-solutions/unit-tests-skills` has no
LICENSE file at time of writing (checked 2026-05-06), so we do NOT
fork its content.** The two-phase verification (compile + execute) is
a common testing convention; the Maven-specific commands and retry
budgets here are written fresh.
