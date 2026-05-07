# Assignment

> **Source-of-truth note** — This document is a **verbatim copy** of the
> course's final-project assignment as posted on Canvas. When this file
> and any project plan disagree, this file wins. AgentTest's reading of
> how each requirement maps to a delivered artifact lives in
> [`project_plan.md`](project_plan.md) § 7 (governance / controls).

---

Build a small GenAI app, skill, or tool for one narrow business use case.

Your project should help a specific user complete a specific workflow:
drafting one type of document, reviewing one kind of clause, extracting
fields from one document type, answering questions from one knowledge
base, preparing one kind of memo, triaging one class of requests, or
something similarly focused.

The goal is not to build the biggest or most complicated system. The
goal is to show that you can design a useful GenAI workflow, explain
the business value, compare it against a simpler baseline, and evaluate
where it works and where it fails.

## What to build

Your final artifact can be an app, skill, tool, or a combination.

If you build an app, it can be Streamlit, Gradio, a small web app, a
command-line app, or something similar. Someone should be able to run
it and use it on at least one example.

If you build a skill or tool, it should be usable by someone working
with an agent. For example, it might be a well-documented Codex skill,
an MCP tool, a callable script with clear inputs and outputs, or a
workflow helper that an agent can reliably invoke.

A notebook or loose script by itself is not enough unless it is clearly
packaged as a usable app, skill, or tool.

Your project should clearly show:

- the user and workflow
- what you built
- why GenAI is useful for this task
- what you compared it against
- what worked, what failed, and where a human should stay involved

## Evaluation

Keep the evaluation simple, but make it real. Do not rely only on
screenshots or one successful example.

Use a small set of realistic examples and compare your project against
a simpler baseline. The baseline can be how the work is done now, the
status quo. It can also be a prompt-only version, keyword search, a
spreadsheet workflow, or another simple approach.

In the README, briefly explain what you tested, what counted as good
output, what the comparison showed, and where the project broke down.

## Requirements and notes

- You may use synthetic data, public data, or real data you have permission to use.
- Do not commit secrets, API keys, private data, or PII to your repository.
- At this point in the course, I recommend using a paid LLM provider account if free tiers or local models slow you down. Keep your usage modest, but do not let access limits prevent you from finishing the project.
- If your project depends on an API key, explain how the grader should provide it in the README. Do not include the key itself.
- Choose the simplest technical design that lets you evaluate the workflow well. Do not use RAG, agents, or multiple models unless they actually help the workflow.

## Lightning Presentation

Final presentations will be 2-3 minutes each.

Your presentation should be short, direct, and focused on the project
as a business workflow. You do not need to explain every technical
detail, and you do not need to run a live demo.

Cover four things:

- **Context, user, and problem** — Who is the user? What workflow are you improving? Why does this problem matter?
- **Solution and design** — What did you build? What are the main GenAI design choices?
- **Evaluation and results** — What did you compare against? What test cases or rubric did you use? What did your evaluation show?
- **Artifact snapshot** — Show brief evidence that the app, skill, or tool exists and works: one screenshot, a short recorded clip, a sample output, or a quick walkthrough of the interface. Do not rely on a live system working perfectly in the moment.

Please rehearse so the presentation fits the time limit. Please use
slides to assist your presentation.

There is no separate project check-in assignment. If you want feedback
before the final presentation, come to office hours or email the
instructor.

## Submission

Submit a GitHub repository link through Canvas.

Your repository should include your app, skill, or tool; any prompts
or scripts needed to run it; dependencies; and a clear README.

The README should include the same four pieces as your presentation,
but in more detail:

- **Context, user, and problem**: who the user is, what workflow you are improving, and why it matters
- **Solution and design**: what you built, how it works, and the key design choices
- **Evaluation and results**: what baseline you compared against, what test cases or rubric you used, and what you found
- **Artifact snapshot**: screenshots, sample inputs/outputs, a short recorded clip, or another concise way to show what the project does

The README should also include setup and usage instructions. A grader
should be able to install the dependencies and run or use the project
on at least one example by following your README.
