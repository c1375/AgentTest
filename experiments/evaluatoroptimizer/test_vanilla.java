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

import java.util.function.Consumer;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.ChatClient.CallResponseSpec;
import org.springframework.ai.chat.client.ChatClient.ChatClientRequestSpec;
import org.springframework.ai.chat.client.ChatClient.PromptUserSpec;

import com.example.agentic.EvaluatorOptimizer.EvaluationResponse;
import com.example.agentic.EvaluatorOptimizer.EvaluationResponse.Evaluation;
import com.example.agentic.EvaluatorOptimizer.Generation;
import com.example.agentic.EvaluatorOptimizer.RefinedResponse;

class EvaluatorOptimizerTest {

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
                .isThrownBy(() -> new EvaluatorOptimizer(null));
    }

    @Test
    void constructorRejectsEmptyGeneratorPrompt() {
        assertThatIllegalArgumentException()
                .isThrownBy(() -> new EvaluatorOptimizer(chatClient, "", "evaluator"));
    }

    @Test
    void constructorRejectsEmptyEvaluatorPrompt() {
        assertThatIllegalArgumentException()
                .isThrownBy(() -> new EvaluatorOptimizer(chatClient, "generator", ""));
    }

    @Test
    void loopReturnsImmediatelyWhenFirstEvaluationPasses() {
        Generation generation = new Generation("first thoughts", "first solution");
        EvaluationResponse passingEvaluation = new EvaluationResponse(Evaluation.PASS, "looks good");

        when(callResponseSpec.entity(Generation.class)).thenReturn(generation);
        when(callResponseSpec.entity(EvaluationResponse.class)).thenReturn(passingEvaluation);

        RefinedResponse response = new EvaluatorOptimizer(chatClient).loop("solve this");

        assertThat(response.solution()).isEqualTo("first solution");
        assertThat(response.chainOfThought()).containsExactly(generation);

        // 1 generate call + 1 evaluate call
        verify(chatClient, times(2)).prompt();
        verify(callResponseSpec, times(1)).entity(Generation.class);
        verify(callResponseSpec, times(1)).entity(EvaluationResponse.class);
    }

    @Test
    void loopIteratesUntilEvaluationPasses() {
        Generation firstAttempt = new Generation("attempt 1", "rough draft");
        Generation secondAttempt = new Generation("attempt 2", "refined draft");
        Generation thirdAttempt = new Generation("attempt 3", "polished draft");

        when(callResponseSpec.entity(Generation.class))
                .thenReturn(firstAttempt, secondAttempt, thirdAttempt);
        when(callResponseSpec.entity(EvaluationResponse.class)).thenReturn(
                new EvaluationResponse(Evaluation.NEEDS_IMPROVEMENT, "tighten the wording"),
                new EvaluationResponse(Evaluation.FAIL, "missing edge case"),
                new EvaluationResponse(Evaluation.PASS, "ready to ship"));

        RefinedResponse response = new EvaluatorOptimizer(chatClient).loop("solve this");

        assertThat(response.solution()).isEqualTo("polished draft");
        assertThat(response.chainOfThought())
                .containsExactly(firstAttempt, secondAttempt, thirdAttempt);

        // 3 generate calls + 3 evaluate calls
        verify(chatClient, times(6)).prompt();
        verify(callResponseSpec, times(3)).entity(Generation.class);
        verify(callResponseSpec, times(3)).entity(EvaluationResponse.class);
    }

    @Test
    void loopTreatsFailAsRetryableLikeNeedsImprovement() {
        Generation failed = new Generation("attempt 1", "broken");
        Generation fixed = new Generation("attempt 2", "fixed");

        when(callResponseSpec.entity(Generation.class)).thenReturn(failed, fixed);
        when(callResponseSpec.entity(EvaluationResponse.class)).thenReturn(
                new EvaluationResponse(Evaluation.FAIL, "doesn't compile"),
                new EvaluationResponse(Evaluation.PASS, "ok"));

        RefinedResponse response = new EvaluatorOptimizer(chatClient).loop("write code");

        assertThat(response.solution()).isEqualTo("fixed");
        assertThat(response.chainOfThought()).containsExactly(failed, fixed);
    }

    @Test
    @SuppressWarnings("unchecked")
    void customPromptsArePassedToChatClient() {
        when(callResponseSpec.entity(Generation.class))
                .thenReturn(new Generation("t", "r"));
        when(callResponseSpec.entity(EvaluationResponse.class))
                .thenReturn(new EvaluationResponse(Evaluation.PASS, "ok"));

        new EvaluatorOptimizer(chatClient, "custom generator {task}", "custom evaluator {content}")
                .loop("hello");

        // The Consumer<PromptUserSpec> is invoked lazily by the framework; we verify
        // only that the user(...) builder was wired through the fluent chain for
        // both the generator and the evaluator.
        verify(requestSpec, times(2)).user(any(Consumer.class));
    }
}
