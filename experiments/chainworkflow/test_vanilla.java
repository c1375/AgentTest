package com.example.agentic;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.ChatClient.CallResponseSpec;
import org.springframework.ai.chat.client.ChatClient.ChatClientRequestSpec;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ChainWorkflowTest {

	private ChatClient chatClient;
	private ChatClientRequestSpec requestSpec;
	private CallResponseSpec callResponseSpec;

	@BeforeEach
	void setUp() {
		chatClient = mock(ChatClient.class);
		requestSpec = mock(ChatClientRequestSpec.class);
		callResponseSpec = mock(CallResponseSpec.class);

		when(chatClient.prompt(anyString())).thenReturn(requestSpec);
		when(requestSpec.call()).thenReturn(callResponseSpec);
	}

	@Test
	void chainReturnsFinalStepResponse() {
		when(callResponseSpec.content()).thenReturn("step1", "step2", "step3", "step4");

		String result = new ChainWorkflow(chatClient).chain("raw input");

		assertThat(result).isEqualTo("step4");
	}

	@Test
	void chainInvokesChatClientOncePerSystemPrompt() {
		when(callResponseSpec.content()).thenReturn("a", "b", "c", "d");
		String[] prompts = { "p1", "p2", "p3", "p4" };

		new ChainWorkflow(chatClient, prompts).chain("input");

		verify(chatClient, times(prompts.length)).prompt(anyString());
		verify(requestSpec, times(prompts.length)).call();
		verify(callResponseSpec, times(prompts.length)).content();
	}

	@Test
	void chainFeedsPreviousResponseIntoNextStep() {
		when(callResponseSpec.content()).thenReturn("first-out", "second-out");
		String[] prompts = { "PROMPT_A", "PROMPT_B" };

		new ChainWorkflow(chatClient, prompts).chain("USER_INPUT");

		ArgumentCaptor<String> inputs = ArgumentCaptor.forClass(String.class);
		verify(chatClient, times(2)).prompt(inputs.capture());
		List<String> calls = inputs.getAllValues();

		assertThat(calls.get(0)).isEqualTo("{PROMPT_A}\n {USER_INPUT}");
		assertThat(calls.get(1)).isEqualTo("{PROMPT_B}\n {first-out}");
	}

	@Test
	void chainWithCustomPromptsUsesProvidedSteps() {
		when(callResponseSpec.content()).thenReturn("only-out");
		String[] prompts = { "single-prompt" };

		String result = new ChainWorkflow(chatClient, prompts).chain("hello");

		assertThat(result).isEqualTo("only-out");
		verify(chatClient, times(1)).prompt(anyString());
	}

	@Test
	void chainWithEmptyPromptsReturnsInputUnchanged() {
		String result = new ChainWorkflow(chatClient, new String[0]).chain("untouched");

		assertThat(result).isEqualTo("untouched");
		verify(chatClient, times(0)).prompt(anyString());
	}
}
