# Runner-helper

Single-file Java program that compiles a (target Java class, generated
JUnit test class) pair and runs the test via JUnit Platform. Used by:

- The **validator's run-on-clean gate**: invokes against the clean target
  → expects PASS; FAIL means the test asserts a false invariant and gets
  dropped before it reaches the user.
- The **eval harness's recall measurement**: invokes against the buggy
  variant → FAIL means the test caught the injected risk.

## One-time setup

```bash
cd engine/eval/runner-helper
python setup.py
```

This downloads JUnit Platform Console Standalone (~6.7 MB) and AssertJ
Core (~1.5 MB) from Maven Central into `lib/`, verifies each against
the published `.sha1` sidecar, and compiles `TestRunner.java` to
`TestRunner.class` next to it.

Requires `javac` (JDK 17+) on `PATH` and Python 3.11+. Re-running the
script is idempotent.

## Invocation

```bash
java -cp 'lib/*:.' \
     -Dagenttest.runner.dir=. \
     TestRunner <target.java> <test.java> <test_class_FQN>
```

Output (single token on first line, details after):

| Token | Exit | Meaning |
|---|---|---|
| `PASS` | 0 | All selected tests passed |
| `FAIL` | 1 | At least one selected test failed (failure trace follows) |
| `COMPILE_FAIL` | 2 | javac diagnostics follow |
| `ERROR` | 3 | Internal error (no JDK, missing test class, etc.) |

The shim under `stubs/` provides a minimal Spring AI API
(`org.springframework.ai.chat.prompt.{Prompt, PromptTemplate}`) so eval
samples that import Spring AI compile without pulling in real Spring AI
+ transitive deps. The shim's behavior is just substitution + content
exposure — enough for LLM01 invariant tests. Extend it if S3+ tests
need richer behavior; keep behavior reproducible.

## Why vendored jars are downloaded, not committed

The lib jars total ~8 MB, which is heavy for a Python project's git
history. `setup.py` downloads them on demand with SHA-1 verification
against Maven Central, so the repo stays small but reproducibility is
preserved. The contents of `lib/*.jar` are gitignored.

## Limitations

- Tests must be in a single class; `TestRunner` selects by class FQN.
- The shim handles `{key}` substitution literally — no escape-sequence
  parsing, no missing-key error. Real Spring AI is stricter.
- `Mockito` is intentionally NOT on the classpath in S2. The generator
  prompt should disallow Mockito imports until S3.
