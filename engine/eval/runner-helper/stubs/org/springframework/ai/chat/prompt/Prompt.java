package org.springframework.ai.chat.prompt;

/**
 * Minimal Spring AI Prompt shim for the AgentTest eval harness.
 *
 * Spring AI's real Prompt has more API surface (messages, options, etc.),
 * but for LLM01 invariant assertions we only need:
 *   - hold the assembled string
 *   - expose it via getContents() and toString()
 *
 * If S3+ tests need richer Spring AI behavior (multi-message Prompt,
 * etc.), extend this shim — keep it small and behavior-clear so the
 * eval results stay reproducible.
 */
public class Prompt {

    private final String contents;

    public Prompt(String contents) {
        this.contents = contents;
    }

    public String getContents() {
        return contents;
    }

    @Override
    public String toString() {
        return contents;
    }
}
