package com.example;

import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.chat.prompt.PromptTemplate;

import java.util.Map;

public class RestaurantPromptAssembler {

    private static final String TEMPLATE =
        "You are a helpful restaurant assistant. User asked: {query}";

    public Prompt assemble(String userQuery) {
        PromptTemplate template = new PromptTemplate(TEMPLATE);
        return template.create(Map.of("query", userQuery));
    }
}
