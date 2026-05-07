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

import java.util.ArrayList;
import java.util.List;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.util.Assert;

/**
 * V_clean variant of {@link com.example.agentic.EvaluatorOptimizer} for
 * AgentTest's Phase 2 stretch precision check. Identical to upstream
 * spring-ai-examples@2a6088d EXCEPT for three OWASP defenses:
 *
 * <ol>
 *   <li><b>LLM01 / ASI01 — direct prompt injection</b>: the user
 *       {@code task} is run through {@link #sanitize(String)} on entry to
 *       {@link #loop(String)} so every generator/evaluator call sees the
 *       cleaned form.</li>
 *   <li><b>LLM01 / ASI04 — indirect injection via evaluator feedback</b>:
 *       the evaluator's {@code feedback} field is run through
 *       {@link #sanitize(String)} before it is appended to the
 *       next-iteration {@code context}, so a poisoned evaluator response
 *       cannot re-inject instructions into the generator.</li>
 *   <li><b>LLM06 / ASI08 — bounded recursion (cascading failures)</b>:
 *       the private recursive {@code loop} now carries an iteration
 *       counter and throws {@link IllegalStateException} when
 *       {@link #MAX_ITERATIONS} is exceeded. Without this cap a
 *       perpetually-NEEDS_IMPROVEMENT evaluator triggers
 *       {@link StackOverflowError}.</li>
 * </ol>
 *
 * <p>The {@link #sanitize(String)} pattern set mirrors
 * {@code rules/owasp/llm01-prompt-injection.md}'s canonical attack-payload
 * inventory — same family used in {@code ChainWorkflow_fixed.java} and
 * {@code OrchestratorWorkers_fixed.java}. The exception message includes
 * the literal {@code "max"} so the skill's Invariant-1 test pattern
 * ({@code assertThatThrownBy.hasMessageContaining("max")}) matches.
 *
 * <p>This file is NOT for production deployment.
 *
 * @author Christian Tzolov (original) — sanitize / max-iter helpers added
 *         by AgentTest for Phase 2 stretch V_clean validation, 2026-05-07.
 * @see <a href=
 *      "https://github.com/spring-projects/spring-ai-examples/blob/2a6088d/agentic-patterns/evaluator-optimizer/src/main/java/com/example/agentic/EvaluatorOptimizer.java">Upstream
 *      EvaluatorOptimizer.java (V_buggy)</a>
 */
@SuppressWarnings("null")
public class EvaluatorOptimizer {

	/**
	 * Hard upper bound on refinement iterations. The evaluator LLM may never
	 * emit PASS (intrinsic difficulty or poisoned response). Without a cap
	 * the recursion runs until StackOverflowError.
	 */
	private static final int MAX_ITERATIONS = 10;

	public static final String DEFAULT_GENERATOR_PROMPT = """
			Your goal is to complete the task based on the input. If there are feedback
			from your previous generations, you should reflect on them to improve your solution.

			CRITICAL: Your response must be a SINGLE LINE of valid JSON with NO LINE BREAKS except those explicitly escaped with \\n.
			Here is the exact format to follow, including all quotes and braces:

			{"thoughts":"Brief description here","response":"public class Example {\\n    // Code here\\n}"}

			Rules for the response field:
			1. ALL line breaks must use \\n
			2. ALL quotes must use \\"
			3. ALL backslashes must be doubled: \\
			4. NO actual line breaks or formatting - everything on one line
			5. NO tabs or special characters
			6. Java code must be complete and properly escaped

			Example of properly formatted response:
			{"thoughts":"Implementing counter","response":"public class Counter {\\n    private int count;\\n    public Counter() {\\n        count = 0;\\n    }\\n    public void increment() {\\n        count++;\\n    }\\n}"}

			Follow this format EXACTLY - your response must be valid JSON on a single line.
			""";

	public static final String DEFAULT_EVALUATOR_PROMPT = """
			Evaluate this code implementation for correctness, time complexity, and best practices.
			Ensure the code have proper javadoc documentation.
			Respond with EXACTLY this JSON format on a single line:

			{"evaluation":"PASS, NEEDS_IMPROVEMENT, or FAIL", "feedback":"Your feedback here"}

			The evaluation field must be one of: "PASS", "NEEDS_IMPROVEMENT", "FAIL"
			Use "PASS" only if all criteria are met with no improvements needed.
			""";

	public static record Generation(String thoughts, String response) {
	}

	public static record EvaluationResponse(Evaluation evaluation, String feedback) {

		public enum Evaluation {
			PASS, NEEDS_IMPROVEMENT, FAIL
		}
	}

	public static record RefinedResponse(String solution, List<Generation> chainOfThought) {
	}

	private final ChatClient chatClient;

	private final String generatorPrompt;

	private final String evaluatorPrompt;

	public EvaluatorOptimizer(ChatClient chatClient) {
		this(chatClient, DEFAULT_GENERATOR_PROMPT, DEFAULT_EVALUATOR_PROMPT);
	}

	public EvaluatorOptimizer(ChatClient chatClient, String generatorPrompt, String evaluatorPrompt) {
		Assert.notNull(chatClient, "ChatClient must not be null");
		Assert.hasText(generatorPrompt, "Generator prompt must not be empty");
		Assert.hasText(evaluatorPrompt, "Evaluator prompt must not be empty");

		this.chatClient = chatClient;
		this.generatorPrompt = generatorPrompt;
		this.evaluatorPrompt = evaluatorPrompt;
	}

	public RefinedResponse loop(String task) {
		List<String> memory = new ArrayList<>();
		List<Generation> chainOfThought = new ArrayList<>();

		// SAFETY: sanitize user task at the entry boundary so all subsequent
		// generator and evaluator calls see the cleaned form.
		String sanitizedTask = sanitize(task);
		return loop(sanitizedTask, "", memory, chainOfThought, 0);
	}

	private RefinedResponse loop(String task, String context, List<String> memory,
			List<Generation> chainOfThought, int iteration) {

		// SAFETY: hard cap on recursion depth. Closes LLM06 / ASI08 surface.
		if (iteration >= MAX_ITERATIONS) {
			throw new IllegalStateException(
					"Evaluator-optimizer exceeded max iterations: " + MAX_ITERATIONS);
		}

		Generation generation = generate(task, context);
		memory.add(generation.response());
		chainOfThought.add(generation);

		EvaluationResponse evaluationResponse = evalute(generation.response(), task);

		if (evaluationResponse.evaluation().equals(EvaluationResponse.Evaluation.PASS)) {
			return new RefinedResponse(generation.response(), chainOfThought);
		}

		StringBuilder newContext = new StringBuilder();
		newContext.append("Previous attempts:");
		for (String m : memory) {
			newContext.append("\n- ").append(m);
		}
		// SAFETY: sanitize evaluator feedback before cycling into the next
		// iteration's context. Closes LLM01 indirect / ASI04 surface — a
		// poisoned evaluator response can't re-inject instructions.
		newContext.append("\nFeedback: ").append(sanitize(evaluationResponse.feedback()));

		return loop(task, newContext.toString(), memory, chainOfThought, iteration + 1);
	}

	private Generation generate(String task, String context) {
		Generation generationResponse = chatClient.prompt()
				.user(u -> u.text("{prompt}\n{context}\nTask: {task}")
						.param("prompt", this.generatorPrompt)
						.param("context", context)
						.param("task", task))
				.call()
				.entity(Generation.class);

		System.out.println(String.format("\n=== GENERATOR OUTPUT ===\nTHOUGHTS: %s\n\nRESPONSE:\n %s\n",
				generationResponse.thoughts(), generationResponse.response()));
		return generationResponse;
	}

	private EvaluationResponse evalute(String content, String task) {

		EvaluationResponse evaluationResponse = chatClient.prompt()
				.user(u -> u.text("{prompt}\nOriginal task: {task}\nContent to evaluate: {content}")
						.param("prompt", this.evaluatorPrompt)
						.param("task", task)
						.param("content", content))
				.call()
				.entity(EvaluationResponse.class);

		System.out.println(String.format("\n=== EVALUATOR OUTPUT ===\nEVALUATION: %s\n\nFEEDBACK: %s\n",
				evaluationResponse.evaluation(), evaluationResponse.feedback()));
		return evaluationResponse;
	}

	/**
	 * Strip canonical OWASP LLM01 attack payload patterns from {@code input}.
	 * Same pattern set as {@code ChainWorkflow_fixed.java} and
	 * {@code OrchestratorWorkers_fixed.java}.
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
