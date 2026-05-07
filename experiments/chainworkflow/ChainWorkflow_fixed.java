package com.example.agentic;

import org.springframework.ai.chat.client.ChatClient;

/**
 * V_clean variant of {@link com.example.agentic.ChainWorkflow} for AgentTest's
 * Phase 2 precision check. Identical to the upstream
 * spring-ai-examples@2a6088d ChainWorkflow.java EXCEPT for the addition of
 * a {@code sanitize(String)} helper applied to the initial user input AND
 * to each LLM response before it cycles into the next step's prompt.
 *
 * <p>The sanitize patterns mirror {@code rules/owasp/llm01-prompt-injection.md}'s
 * canonical attack-payload set — strip template-breakout chars, instruction-shape
 * phrases, conversation-turn markers, and Llama instruction tags.
 *
 * <p>This file is NOT for production deployment. It is the "fixed" baseline
 * AgentTest's generated test class is run against to confirm tests PASS on
 * defended code (precision check).
 *
 * @author Christian Tzolov (original) — sanitize() helper added by AgentTest
 *         for Phase 2 V_clean validation, 2026-05-06.
 * @see <a href=
 *      "https://github.com/spring-projects/spring-ai-examples/blob/2a6088d/agentic-patterns/chain-workflow/src/main/java/com/example/agentic/ChainWorkflow.java">Upstream
 *      ChainWorkflow.java (V_buggy)</a>
 */
public class ChainWorkflow {

	private static final String[] DEFAULT_SYSTEM_PROMPTS = {

			// Step 1
			"""
					Extract only the numerical values and their associated metrics from the text.
					Format each as'value: metric' on a new line.
					Example format:
					92: customer satisfaction
					45%: revenue growth""",
			// Step 2
			"""
					Convert all numerical values to percentages where possible.
					If not a percentage or points, convert to decimal (e.g., 92 points -> 92%).
					Keep one number per line.
					Example format:
					92%: customer satisfaction
					45%: revenue growth""",
			// Step 3
			"""
					Sort all lines in descending order by numerical value.
					Keep the format 'value: metric' on each line.
					Example:
					92%: customer satisfaction
					87%: employee satisfaction""",
			// Step 4
			"""
					Format the sorted data as a markdown table with columns:
					| Metric | Value |
					|:--|--:|
					| Customer Satisfaction | 92% | """
	};

	private final ChatClient chatClient;

	private final String[] systemPrompts;

	public ChainWorkflow(ChatClient chatClient) {
		this(chatClient, DEFAULT_SYSTEM_PROMPTS);
	}

	public ChainWorkflow(ChatClient chatClient, String[] systemPrompts) {
		this.chatClient = chatClient;
		this.systemPrompts = systemPrompts;
	}

	public String chain(String userInput) {

		int step = 0;
		// SAFETY: sanitize the initial user input. Removing this returns to the
		// upstream LLM01 vulnerability.
		String response = sanitize(userInput);
		System.out.println(String.format("\nSTEP %s:\n %s", step++, response));

		for (String prompt : systemPrompts) {

			// 1. Compose the input using the response from the previous step.
			String input = String.format("{%s}\n {%s}", prompt, response);

			// 2. Call the chat client with the new input.
			// SAFETY: sanitize the LLM response before it cycles into the next
			// step's prompt. This closes the indirect-injection surface — even
			// if the LLM "complies" with an injection at step N, step N+1's
			// prompt is still clean.
			response = sanitize(chatClient.prompt(input).call().content());

			System.out.println(String.format("\nSTEP %s:\n %s", step++, response));
		}

		return response;
	}

	/**
	 * Strip the canonical OWASP LLM01 attack payload patterns from {@code input}.
	 * Aligned with {@code rules/owasp/llm01-prompt-injection.md}.
	 */
	private static String sanitize(String input) {
		return input.replaceAll("[{}]", "")
				.replaceAll("(?i)\\bignore\\s+(?:above|previous)\\b", "")
				.replaceAll("(?i)\\b(?:system|assistant)\\s*:", "")
				.replaceAll("(?i)<\\|im_(?:end|start)\\|>", "")
				.replaceAll("(?i)\\[/?INST\\]", "");
	}
}
