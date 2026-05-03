# Course Assignment — Final Project (Generative AI)

This document records the course assignment requirements verbatim. It is the
**source of truth** for what the final deliverable must satisfy. Any conflict
between project plans and this file should resolve in favor of this file.

---

## Assignment

Build a small GenAI app, skill, or tool for one narrow business use case.

Your project should help a specific user complete a specific workflow:
drafting one type of document, reviewing one kind of clause, extracting fields
from one document type, answering questions from one knowledge base, preparing
one kind of memo, triaging one class of requests, or something similarly
focused.

The goal is **not** to build the biggest or most complicated system. The goal
is to show that you can:

- Design a useful GenAI workflow
- Explain the business value
- Compare it against a simpler baseline
- Evaluate where it works and where it fails

## What to build

The final artifact can be an app, skill, tool, or a combination.

- **App**: Streamlit, Gradio, a small web app, a command-line app, or
  similar. Someone should be able to run it and use it on at least one
  example.
- **Skill / tool**: usable by someone working with an agent. For example,
  a well-documented Codex skill, an MCP tool, a callable script with clear
  inputs and outputs, or a workflow helper that an agent can reliably invoke.

A notebook or loose script by itself is **not enough** unless it is clearly
packaged as a usable app, skill, or tool.

The project must clearly show:

1. The user and workflow
2. What you built
3. Why GenAI is useful for this task
4. What you compared it against
5. What worked, what failed, and where a human should stay involved

## Evaluation

Keep the evaluation **simple, but make it real**. Do not rely only on
screenshots or one successful example.

Use a small set of realistic examples and compare your project against a
simpler baseline. The baseline can be:

- How the work is done now (status quo)
- A prompt-only version
- Keyword search
- A spreadsheet workflow
- Another simple approach

In the README, briefly explain:

- What you tested
- What counted as good output
- What the comparison showed
- Where the project broke down

## Requirements and notes

- May use synthetic data, public data, or real data with permission
- **Do not commit secrets, API keys, private data, or PII** to the repository
- A paid LLM provider account is recommended if free tiers slow you down
- If the project depends on an API key, explain in the README how the grader
  should provide it. **Do not include the key itself.**
- Choose the **simplest technical design** that lets you evaluate the workflow
  well. **Do not use RAG, agents, or multiple models unless they actually
  help the workflow.**

## Lightning presentation

- 2–3 minutes
- Short, direct, focused on the project as a business workflow
- No need to explain every technical detail
- No need to run a live demo
- Slides required

Cover four things:

1. **Context, user, and problem** — Who is the user? What workflow are you
   improving? Why does this problem matter?
2. **Solution and design** — What did you build? What are the main GenAI
   design choices?
3. **Evaluation and results** — What did you compare against? What test
   cases or rubric did you use? What did your evaluation show?
4. **Artifact snapshot** — One screenshot, short clip, sample output, or
   quick walkthrough showing the artifact exists and works. Do not rely on
   a live system working perfectly.

## Submission

GitHub repository link via Canvas.

Repository must include:

- The app, skill, or tool
- Any prompts or scripts needed to run it
- Dependencies
- A clear README

The README must include the same four pieces as the presentation, in more
detail:

1. **Context, user, and problem** — who the user is, what workflow you are
   improving, why it matters
2. **Solution and design** — what you built, how it works, key design
   choices
3. **Evaluation and results** — baseline compared against, test cases or
   rubric used, what you found
4. **Artifact snapshot** — screenshots, sample inputs/outputs, short clip,
   or another concise demonstration

The README must also include **setup and usage instructions**. A grader must
be able to install dependencies and run the project on at least one example
by following the README.

---

## Constraints derived from the assignment (quick reference)

These are the implications that bind every design decision.

### Scope discipline

- **Narrow workflow** — one user, one workflow. Not a platform.
- **Simplest design that lets evaluation work**. RAG, multi-model, multi-stage
  pipelines must each **earn their place** by demonstrably improving over a
  simpler version. If an ablation shows a component doesn't help, **drop it
  from the deliverable** rather than defending it.

### Evaluation discipline

- **Small but real**. The assignment explicitly says small is fine — what
  matters is that the eval reflects realistic examples, not cherry-picks.
- **Mandatory baseline comparison**. Pick one, justify it, run it.
- **Document what counts as good output** before measuring. Don't define the
  rubric after seeing the numbers.
- **Report failures honestly**. "Where it broke down" is a required README
  section.

### Deliverable discipline

- **Runnable by grader**. README must walk a stranger from clone → working
  example. Test this by reading the README cold.
- **No secrets in repo**. `.env` patterns, key-injection instructions in
  README.
- **Artifact must exist as a real, runnable thing** — app / CLI / skill /
  MCP tool / Codex skill. A notebook alone fails.
- **Lightning presentation is 2–3 minutes**. The pitch must compress to that.
  If the pitch needs more than 3 minutes to land, the scope is too wide.

### Human-in-the-loop framing

- "Where a human should stay involved" is a required section. This is not
  optional. The deliverable must explicitly mark which decisions remain
  human even after the tool runs.
