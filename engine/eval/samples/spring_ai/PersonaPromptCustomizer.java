package com.example.spring;

import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.chat.prompt.PromptTemplate;

import java.util.Map;

/**
 * Persona-aware prompt customizer. A user-configurable persona string
 * (saved in the user profile elsewhere, loaded here) splices into the
 * system message so the assistant adopts that persona for the
 * conversation. Used in chatbot platforms where each user can
 * customize their assistant's tone or character.
 *
 * The clean version sanitizes the persona before concatenation into
 * the system text. The persona is user-controlled and lands on the
 * system-side of the prompt — a higher-trust position than the user
 * query slot. The llm01_remove_sanitization injection neutralizes
 * the sanitize() helper to a passthrough, letting a hostile persona
 * carry role-flip ("system: ...") or instruction-override ("ignore
 * above") payloads that override the baseline assistant behavior.
 */
public class PersonaPromptCustomizer {

    private static final String BASE_SYSTEM =
        "You are a helpful assistant. Keep replies concise and respectful.";

    public Prompt build(String userPersona, String userQuery) {
        // SAFETY: persona splices directly into the system message via
        // string concatenation — sanitize so the persona cannot smuggle
        // role-flip or instruction-override payloads into the
        // system-side position. The user query is sanitized for the
        // same reason before substitution.
        String safePersona = sanitize(userPersona);

        String systemMessage = BASE_SYSTEM + "\n\nPersona: " + safePersona;
        PromptTemplate template = new PromptTemplate(
            systemMessage + "\n\nUser: {query}"
        );
        return template.create(Map.of("query", sanitize(userQuery)));
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
