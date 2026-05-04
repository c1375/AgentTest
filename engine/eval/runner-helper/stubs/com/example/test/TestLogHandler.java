package com.example.test;

import java.text.MessageFormat;
import java.util.ArrayList;
import java.util.List;
import java.util.logging.Handler;
import java.util.logging.LogRecord;

/*
 * Captures java.util.logging records into an in-memory buffer for
 * assertion in LLM02 (Sensitive Information Disclosure) tests.
 *
 * Usage from a generated test:
 *   TestLogHandler handler = new TestLogHandler();
 *   Logger.getLogger("com.example").addHandler(handler);
 *   target.doSomething(reqContainingSentinel);
 *   assertThat(handler.capturedText()).doesNotContain("SENTINEL_TOKEN");
 *
 * Lives under engine/eval/runner-helper/stubs/ so the TestRunner picks
 * it up via the existing recursive shim-source walk. JUL was chosen
 * over SLF4J for S3 to avoid the SLF4J-binding shim work; the realism
 * trade-off is documented in docs/plan/sprint-3.md § 1.
 */
public class TestLogHandler extends Handler {

    private final List<String> records = new ArrayList<>();

    @Override
    public synchronized void publish(LogRecord record) {
        if (record == null) {
            return;
        }
        String message = record.getMessage();
        if (message == null) {
            return;
        }
        Object[] params = record.getParameters();
        String formatted;
        if (params != null && params.length > 0) {
            try {
                formatted = MessageFormat.format(message, params);
            } catch (IllegalArgumentException ex) {
                // Message wasn't a MessageFormat pattern (e.g., logger.info("foo: " + s)).
                // Fall back to the raw template — better than dropping the record.
                formatted = message;
            }
        } else {
            formatted = message;
        }
        records.add(formatted);
    }

    @Override
    public void flush() { }

    @Override
    public void close() { }

    /** Concatenated text of every captured record, newline-separated. */
    public synchronized String capturedText() {
        return String.join("\n", records);
    }

    /** Defensive snapshot of the per-record list. Useful when a test wants per-record assertions. */
    public synchronized List<String> capturedRecords() {
        return new ArrayList<>(records);
    }
}
