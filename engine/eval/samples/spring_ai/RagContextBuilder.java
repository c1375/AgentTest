package com.example.spring;

import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.chat.prompt.PromptTemplate;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * RAG (retrieval-augmented generation) context builder. Concatenates
 * retrieved documents into a Spring AI PromptTemplate variable so the
 * model can answer using external knowledge.
 *
 * Retrieved documents may originate from user uploads, public crawls,
 * or third-party APIs and are therefore untrusted — this is the
 * "indirect prompt injection" surface called out in OWASP LLM01.
 *
 * The clean version sanitizes each document and the user question
 * before template substitution. The llm01_remove_sanitization
 * injection neutralizes the sanitize() helper to a passthrough,
 * letting a poisoned document smuggle template-breakout or
 * instruction-shaped payloads into the assembled prompt.
 */
public class RagContextBuilder {

    private static final String TEMPLATE =
        "Use the following retrieved context to answer the user's question.\n" +
        "Context:\n{context}\n\n" +
        "Question: {question}";

    public Prompt buildWithContext(List<String> retrievedDocs, String question) {
        // SAFETY: each retrieved document is untrusted external content
        // (RAG-poisoning surface) and must be sanitized before
        // concatenation. The question is direct user input and is
        // sanitized at the same boundary.
        StringBuilder ctx = new StringBuilder();
        for (String doc : retrievedDocs) {
            ctx.append(sanitize(doc)).append("\n---\n");
        }

        Map<String, Object> vars = new HashMap<>();
        vars.put("context", ctx.toString());
        vars.put("question", sanitize(question));

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
