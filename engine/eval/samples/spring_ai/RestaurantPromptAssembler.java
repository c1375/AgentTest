package com.example.spring;

import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.chat.prompt.PromptTemplate;

import java.util.Map;

/**
 * Restaurant assistant prompt assembler. Uses Spring AI's PromptTemplate
 * with a static system message and a sanitization pass over the user's
 * query before substitution.
 *
 * The clean version sanitizes user input before interpolation. The
 * llm01_remove_sanitization injection neutralizes the sanitize() helper
 * to a passthrough, letting raw user input (including template-breakout
 * payloads) flow into the assembled prompt.
 */
public class RestaurantPromptAssembler {

    private static final String TEMPLATE =
        "You are a helpful restaurant assistant. " +
        "Answer the user's query: {query}";

    public Prompt assemble(String userQuery) {
        // SAFETY: sanitize the user query before template substitution.
        // Any template-breakout characters or instruction-shaped phrases
        // are stripped here.
        String safeQuery = sanitize(userQuery);

        PromptTemplate template = new PromptTemplate(TEMPLATE);
        return template.create(Map.of("query", safeQuery));
    }

    private static String sanitize(String input) {
        // Strip the canonical prompt-injection payloads listed in the
        // OWASP LLM01 invariant. Removing this is the LLM01 injection.
        return input.replaceAll("[{}]", "")
                    .replaceAll("(?i)\\bignore\\s+(?:above|previous)\\b", "")
                    .replaceAll("(?i)\\b(?:system|assistant)\\s*:", "")
                    .replaceAll("(?i)<\\|im_(?:end|start)\\|>", "")
                    .replaceAll("(?i)\\[/?INST\\]", "");
    }
}
