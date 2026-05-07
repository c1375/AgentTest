# Post-generation verification (compile + execute)

Runs after the test code is generated (`SKILL.md` Step 6). Mechanically
verifies the test compiles and that expected outcomes hold. **Never
deliver tests that don't compile.**

## Step 6.1: Compile preflight

```bash
cd <project_root>  # the user's Maven project root (where pom.xml is)
./mvnw test-compile -q 2>&1 | tail -30
# OR if mvnw not present:
mvn test-compile -q 2>&1 | tail -30
```

### Success
- Exit 0
- No "BUILD FAILURE" in output
→ continue to 6.2

### Failure (max 5 attempts)

Read the diagnostic. Common issues + fixes:

| Diagnostic | Likely cause | Fix |
|---|---|---|
| `cannot find symbol: class XYZ` | Missing import | Add `import com.foo.XYZ;` |
| `cannot find symbol: method abc()` | Wrong method name OR method doesn't exist on target | Re-read target source; use ONLY symbols present there |
| `incompatible types: A cannot be converted to B` | Mock return type mismatch | Check `when(...).thenReturn(...)` types; for `Flux<String>` use `Flux.just(...)` |
| `package org.assertj.core.api does not exist` | AssertJ not on test classpath | Verify `spring-boot-starter-test` is in `pom.xml`; if absent, fall back to `org.junit.jupiter.api.Assertions.*` (less expressive but always available) |
| `package org.mockito does not exist` | Mockito not on classpath | Same as AssertJ — usually `spring-boot-starter-test` brings it |
| `package org.springframework.ai... does not exist` | Spring AI not on test classpath | Verify in `pom.xml`. If absent, target is not actually a Spring AI project — refuse |

After fix, re-run `mvn test-compile -q`.

**Stop after 5 attempts even if still failing.** Deliver source + warning
("test source generated but did not compile after 5 retry attempts;
manual review required") — don't loop forever.

## Step 6.2: Run on current target (V_buggy if it has the OWASP risk)

```bash
./mvnw test -Dtest=<TargetClass>AgentGenTest -q 2>&1 | tail -50
```

Record per-method outcome:
- `Tests run: X, Failures: Y, Errors: Z, Skipped: W`
- For each failed test: capture the assertion failure message

If the target has the OWASP risk (e.g., upstream `ChainWorkflow.java`),
attack-payload-assertion tests SHOULD fail — that means they caught
the risk.

**Apply catch criterion** (regex below; this rule is self-contained, not
dependent on external project docs):

- Failure with assertion message matching
  `(?i)(sanitize|injection|template.?breakout|system\s*:|prompt.?inject)` →
  CATCH ✓ (the test detected an OWASP-shape failure)
- Failure with other assertion message → may be a wrong test, refine
- ERROR (uncaught exception) → likely test bug, fix the test

## Step 6.3: Run on V_clean (if user provides one)

If the user has a "fixed" version of the target file (e.g., they wrote
a `sanitize()` helper):

1. User swaps in V_clean (manual `cp` or version control)
2. Re-run `./mvnw test -Dtest=<TargetClass>AgentGenTest -q`
3. Tests should PASS on V_clean (no false positives → precision ✓)

If any test FAILs on V_clean → assertion is too strict.

### Failure on V_clean (max 3 attempts)

Inspect the failure:
- Assertion text reveals what was asserted
- Compare V_clean and V_buggy diff to see what changed
- Refine the test (NEVER modify production code — neither V_buggy
  nor V_clean)
- Common refinements:
  - Loosen exact-match `isEqualTo` → `contains` / `doesNotContain`
  - Add edge case to mock setup (e.g., `responseSpec.content()` returns
    something `sanitize()` can roundtrip through)
  - Drop assertion that conflates two concerns

If still failing after 3 attempts → drop that test method, log as
"could not stabilize", report.

## Step 6.4: Report outcomes

In the conversation, print a structured summary:

```
=== Compile preflight ===
BUILD SUCCESS (passed in N retries)

=== V_buggy run (current target) ===
Tests run: 4, Failures: 3, Errors: 0
- chain_userInputContainsTemplateBreakout: FAIL ✓ catch
  (assertion: ".doesNotContain('}}')")
- chain_userInputContainsImStartTag: FAIL ✓ catch
  (assertion: ".doesNotContain('<|im_start|>')")
- chain_normalInput: PASS (sanity check)
- chain_emptyInput: ERROR — NPE in test setup, fix needed

=== V_clean run (if available) ===
Tests run: 4, Failures: 0, Errors: 0
All tests PASS ✓ precision
```

## Build system support

This skill assumes Maven. **Gradle / other build systems not yet
supported** — refuse early in `SKILL.md` Step 1 if `pom.xml` is not
present in the project root.

For non-Maven projects, instruct the user to manually compile + run
tests, but skip the retry-loop automation. Print the test source +
note: "verification step skipped (project is not Maven)."

## Source

Original to AgentTest. The two-phase compile + execute verification is
common testing practice; the Maven-specific commands and retry budgets
here are AgentTest-specific implementation choices.
