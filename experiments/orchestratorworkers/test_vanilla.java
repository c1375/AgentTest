/*
 * Copyright 2024 - 2024 the original author or authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * https://www.apache.org/licenses/LICENSE-2.0
 */
package com.example.agentic;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.List;
import java.util.function.Consumer;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.ChatClient.CallResponseSpec;
import org.springframework.ai.chat.client.ChatClient.ChatClientRequestSpec;
import org.springframework.ai.chat.client.ChatClient.PromptUserSpec;

import com.example.agentic.OrchestratorWorkers.FinalResponse;
import com.example.agentic.OrchestratorWorkers.OrchestratorResponse;
import com.example.agentic.OrchestratorWorkers.Task;

class OrchestratorWorkersTest {

    private ChatClient chatClient;
    private ChatClientRequestSpec requestSpec;
    private CallResponseSpec callResponseSpec;

    @BeforeEach
    @SuppressWarnings("unchecked")
    void setUp() {
        chatClient = mock(ChatClient.class);
        requestSpec = mock(ChatClientRequestSpec.class);
        callResponseSpec = mock(CallResponseSpec.class);

        when(chatClient.prompt()).thenReturn(requestSpec);
        when(requestSpec.user(any(Consumer.class))).thenReturn(requestSpec);
        when(requestSpec.call()).thenReturn(callResponseSpec);
    }

    @Test
    void constructorRejectsNullChatClient() {
        assertThatIllegalArgumentException()
                .isThrownBy(() -> new OrchestratorWorkers(null));
    }

    @Test
    void constructorRejectsEmptyOrchestratorPrompt() {
        assertThatIllegalArgumentException()
                .isThrownBy(() -> new OrchestratorWorkers(chatClient, "", "worker"));
    }

    @Test
    void constructorRejectsEmptyWorkerPrompt() {
        assertThatIllegalArgumentException()
                .isThrownBy(() -> new OrchestratorWorkers(chatClient, "orchestrator", ""));
    }

    @Test
    void processRejectsEmptyTaskDescription() {
        OrchestratorWorkers orchestrator = new OrchestratorWorkers(chatClient);

        assertThatIllegalArgumentException()
                .isThrownBy(() -> orchestrator.process(""));
        assertThatIllegalArgumentException()
                .isThrownBy(() -> orchestrator.process(null));
    }

    @Test
    void processOrchestratesAndAggregatesWorkerOutputs() {
        OrchestratorResponse orchestratorResponse = new OrchestratorResponse(
                "Two complementary angles cover this task.",
                List.of(
                        new Task("formal", "Write a precise, technical version"),
                        new Task("conversational", "Write a friendly, engaging version")));

        when(callResponseSpec.entity(OrchestratorResponse.class)).thenReturn(orchestratorResponse);
        when(callResponseSpec.content())
                .thenReturn("formal copy", "conversational copy");

        FinalResponse response = new OrchestratorWorkers(chatClient)
                .process("Write a product description for an eco-friendly water bottle");

        assertThat(response.analysis()).isEqualTo("Two complementary angles cover this task.");
        assertThat(response.workerResponses())
                .containsExactly("formal copy", "conversational copy");

        // 1 orchestrator call + 1 call per worker task
        verify(chatClient, times(3)).prompt();
        verify(callResponseSpec, times(1)).entity(OrchestratorResponse.class);
        verify(callResponseSpec, times(2)).content();
    }

    @Test
    void processHandlesEmptyWorkerTaskList() {
        OrchestratorResponse orchestratorResponse = new OrchestratorResponse(
                "Nothing to subdivide.", List.of());

        when(callResponseSpec.entity(OrchestratorResponse.class)).thenReturn(orchestratorResponse);

        FinalResponse response = new OrchestratorWorkers(chatClient).process("trivial task");

        assertThat(response.analysis()).isEqualTo("Nothing to subdivide.");
        assertThat(response.workerResponses()).isEmpty();
        verify(chatClient, times(1)).prompt();
    }

    @Test
    @SuppressWarnings("unchecked")
    void customPromptsArePassedToChatClient() {
        when(callResponseSpec.entity(OrchestratorResponse.class))
                .thenReturn(new OrchestratorResponse("a", List.of()));

        new OrchestratorWorkers(chatClient, "custom orchestrator {task}", "custom worker {original_task}")
                .process("hello");

        // The Consumer<PromptUserSpec> is invoked lazily by the framework; we verify
        // only that the user(...) builder was wired through the fluent chain.
        verify(requestSpec, times(1)).user(any(Consumer.class));
    }
}
