/*
* Copyright 2024 - 2024 the original author or authors.
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
* https://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*/
package com.example.agentic;

import java.util.List;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.util.Assert;

/**
 * V_clean variant of {@link com.example.agentic.OrchestratorWorkers} for
 * AgentTest's Phase 2 stretch precision check. Identical to upstream
 * spring-ai-examples@2a6088d EXCEPT for three OWASP defenses:
 *
 * <ol>
 *   <li><b>LLM01 / ASI01 — direct prompt injection</b>: {@code taskDescription}
 *       is run through {@link #sanitize(String)} before being substituted into
 *       the orchestrator prompt's {@code task} parameter.</li>
 *   <li><b>ASI07 — insecure inter-agent communication</b>: each
 *       {@code task.type()} and {@code task.description()} field returned by
 *       the orchestrator LLM is run through {@link #sanitize(String)} before
 *       being substituted into the worker prompt parameters.</li>
 *   <li><b>LLM06 / ASI08 — bounded fan-out (cascading failures)</b>: the
 *       orchestrator's {@code tasks} list is capped at {@link #MAX_WORKERS}
 *       entries (silently truncated). Without this cap a runaway or poisoned
 *       orchestrator response could fan out to arbitrarily many worker LLM
 *       calls.</li>
 * </ol>
 *
 * <p>The {@link #sanitize(String)} pattern set mirrors
 * {@code rules/owasp/llm01-prompt-injection.md}'s canonical attack-payload
 * inventory (template-breakout chars, instruction-shape phrases, conversation
 * markers, Llama instruction tags) — same family used in {@code
 * ChainWorkflow_fixed.java}.
 *
 * <p>This file is NOT for production deployment. It is the "fixed" baseline
 * AgentTest's generated test class is run against to confirm tests PASS on
 * defended code (precision check). Truncate-not-throw was chosen to match
 * the skill test pattern (no try/catch around {@code .process(...)}).
 *
 * @author Christian Tzolov (original) — sanitize / cap helpers added by
 *         AgentTest for Phase 2 stretch V_clean validation, 2026-05-07.
 * @see <a href=
 *      "https://github.com/spring-projects/spring-ai-examples/blob/2a6088d/agentic-patterns/orchestrator-workers/src/main/java/com/example/agentic/OrchestratorWorkers.java">Upstream
 *      OrchestratorWorkers.java (V_buggy)</a>
 */
public class OrchestratorWorkers {

	/**
	 * Hard upper bound on the number of subtasks the orchestrator may emit.
	 * Untrusted LLM output without a cap can spawn arbitrary worker LLM calls.
	 */
	private static final int MAX_WORKERS = 10;

	private final ChatClient chatClient;
	private final String orchestratorPrompt;
	private final String workerPrompt;

	public static final String DEFAULT_ORCHESTRATOR_PROMPT = """
			Analyze this task and break it down into 2-3 distinct approaches:

			Task: {task}

			Return your response in this JSON format:
			\\{
			"analysis": "Explain your understanding of the task and which variations would be valuable.
			             Focus on how each approach serves different aspects of the task.",
			"tasks": [
				\\{
				"type": "formal",
				"description": "Write a precise, technical version that emphasizes specifications"
				\\},
				\\{
				"type": "conversational",
				"description": "Write an engaging, friendly version that connects with readers"
				\\}
			]
			\\}
			""";

	public static final String DEFAULT_WORKER_PROMPT = """
			Generate content based on:
			Task: {original_task}
			Style: {task_type}
			Guidelines: {task_description}
			""";

	public static record Task(String type, String description) {
	}

	public static record OrchestratorResponse(String analysis, List<Task> tasks) {
	}

	public static record FinalResponse(String analysis, List<String> workerResponses) {
	}

	public OrchestratorWorkers(ChatClient chatClient) {
		this(chatClient, DEFAULT_ORCHESTRATOR_PROMPT, DEFAULT_WORKER_PROMPT);
	}

	public OrchestratorWorkers(ChatClient chatClient, String orchestratorPrompt, String workerPrompt) {
		Assert.notNull(chatClient, "ChatClient must not be null");
		Assert.hasText(orchestratorPrompt, "Orchestrator prompt must not be empty");
		Assert.hasText(workerPrompt, "Worker prompt must not be empty");

		this.chatClient = chatClient;
		this.orchestratorPrompt = orchestratorPrompt;
		this.workerPrompt = workerPrompt;
	}

	@SuppressWarnings("null")
	public FinalResponse process(String taskDescription) {
		Assert.hasText(taskDescription, "Task description must not be empty");

		// SAFETY: sanitize user input before substituting into orchestrator
		// prompt. Closes LLM01 direct prompt-injection surface.
		final String sanitizedTask = sanitize(taskDescription);

		// Step 1: Get orchestrator response
		OrchestratorResponse orchestratorResponse = this.chatClient.prompt()
				.user(u -> u.text(this.orchestratorPrompt)
						.param("task", sanitizedTask))
				.call()
				.entity(OrchestratorResponse.class);

		System.out.println(String.format("\n=== ORCHESTRATOR OUTPUT ===\nANALYSIS: %s\n\nTASKS: %s\n",
				orchestratorResponse.analysis(), orchestratorResponse.tasks()));

		// SAFETY: cap LLM-controlled task list to MAX_WORKERS. Closes LLM06 /
		// ASI08 cascading-failure surface (orchestrator can't trigger more
		// than MAX_WORKERS worker LLM calls regardless of what the LLM emits).
		List<Task> taskList = orchestratorResponse.tasks();
		if (taskList == null) {
			taskList = List.of();
		}
		if (taskList.size() > MAX_WORKERS) {
			taskList = taskList.subList(0, MAX_WORKERS);
		}

		// Step 2: Process each task
		// SAFETY: sanitize orchestrator-emitted task fields before substituting
		// into worker prompts. Closes ASI07 inter-agent-comm surface — even if
		// the orchestrator LLM "complies" with an injection, the worker prompts
		// don't carry the payload verbatim.
		List<String> workerResponses = taskList.stream().map(task -> this.chatClient.prompt()
				.user(u -> u.text(this.workerPrompt)
						.param("original_task", sanitizedTask)
						.param("task_type", sanitize(task.type()))
						.param("task_description", sanitize(task.description())))
				.call()
				.content()).toList();

		System.out.println("\n=== WORKER OUTPUT ===\n" + workerResponses);

		return new FinalResponse(orchestratorResponse.analysis(), workerResponses);
	}

	/**
	 * Strip canonical OWASP LLM01 attack payload patterns from {@code input}.
	 * Same pattern set as {@code ChainWorkflow_fixed.java}; aligned with
	 * {@code rules/owasp/llm01-prompt-injection.md}.
	 */
	private static String sanitize(String input) {
		if (input == null) {
			return "";
		}
		return input.replaceAll("[{}]", "")
				.replaceAll("(?i)\\bignore\\b(?:\\s+\\w+){0,3}\\s+(?:above|previous|prior)\\b", "")
				.replaceAll("(?i)\\b(?:system|assistant)\\s*:", "")
				.replaceAll("(?i)<\\|im_(?:end|start)\\|>", "")
				.replaceAll("(?i)\\[/?INST\\]", "");
	}

}
