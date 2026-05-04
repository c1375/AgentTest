package com.example.spring;

import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.chat.prompt.PromptTemplate;

import java.util.HashMap;
import java.util.Map;

/**
 * Email drafting prompt assembler. Two user-controlled variables
 * (intent and recipient) flow into a Spring AI PromptTemplate. Both
 * are sanitized before substitution in the clean version.
 *
 * The llm01_remove_sanitization injection neutralizes the sanitize()
 * helper to a passthrough. Either variable can then carry a
 * template-breakout payload that lands in the assembled prompt
 * verbatim.
 */
public class EmailDraftingAssembler {

    private static final String TEMPLATE =
        "Draft a professional email about {intent} addressed to {recipient}.";

    public Prompt drafts(String userIntent, String recipient) {
        // SAFETY: both inputs are user-controlled and must be sanitized
        // before they hit the template's substitution boundary.
        Map<String, Object> vars = new HashMap<>();
        vars.put("intent", sanitize(userIntent));
        vars.put("recipient", sanitize(recipient));

        PromptTemplate template = new PromptTemplate(TEMPLATE);
        return template.create(vars);
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
