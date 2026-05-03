package org.springframework.ai.chat.prompt;

import java.util.Map;

/**
 * Minimal Spring AI PromptTemplate shim for the AgentTest eval harness.
 *
 * Substitution is a literal `{key}` -> `value` replacement, applied for
 * every entry in the Map. Variables not present in the Map are left
 * unsubstituted (matching Spring AI's default behavior on missing keys).
 *
 * The shim is intentionally simple: the LLM01 invariant only needs the
 * substituted string to actually carry the user input — anything fancier
 * (StringTemplateRenderer options, ChatMessage flavors) doesn't change
 * what an injection-detecting test asserts.
 */
public class PromptTemplate {

    private final String template;

    public PromptTemplate(String template) {
        this.template = template;
    }

    public Prompt create(Map<String, Object> variables) {
        String result = template;
        for (Map.Entry<String, Object> entry : variables.entrySet()) {
            String placeholder = "{" + entry.getKey() + "}";
            result = result.replace(placeholder, String.valueOf(entry.getValue()));
        }
        return new Prompt(result);
    }
}
