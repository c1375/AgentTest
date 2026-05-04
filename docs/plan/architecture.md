# Architecture Plan

This document locks the engineering decisions that `docs/project_plan.md`
intentionally leaves vague. The project plan is the deliverable face shown to
the grader; this file is the per-decision record that S1+ implementation
work depends on.

When this file and `docs/project_plan.md` disagree, **this file wins for
implementation**, and `docs/project_plan.md` should be updated to match.
Cascading edits owed to the project plan are tracked at the bottom.

---

## Locked decisions

### 1. CLI ↔ engine: in-process by default, HTTP optional

The CLI is the grader-facing artifact. A grader runs
`python -m agenttest.cli generate Foo.java` immediately after `pip install`
— **before** any uvicorn server is up. Three options were considered:

| Option | Pro | Con |
|---|---|---|
| A. In-process direct call to pipeline funcs | Simple, no server | CLI and skill take different code paths → eval less representative |
| B. CLI auto-spawns uvicorn subprocess | Single command for grader | Subprocess lifecycle is fragile |
| **C. In-process by default, `--server URL` opt-in for HTTP** | Single command for grader, eval can opt into HTTP mode for skill-parity | Two code paths to maintain, but they share the pipeline core |

**Decision: C.**

- Default invocation: `python -m agenttest.cli generate Foo.java` runs the
  pipeline in-process via `asyncio.run(...)`. Progress prints to stdout.
- Opt-in: `python -m agenttest.cli generate Foo.java --server http://localhost:8000`
  posts to the FastAPI engine and consumes the SSE stream. Used by the eval
  harness when measuring skill-parity behavior.
- The shared core is `engine/src/agenttest/pipeline.py` — a single async
  function that takes the input class and yields events. Both the CLI and
  the FastAPI route call it.

### 2. Java AST: `javalang` (pure Python)

Two candidates from `project_plan.md` § 7:

| Option | Pro | Con |
|---|---|---|
| **`javalang`** | pip-installable, zero-config, sufficient for Java 17 | weak on Java 22+ (records pattern matching), maintained but slowly |
| JavaParser via subprocess (Java helper emits AST as JSON) | accurate on latest Java, robust | adds Java toolchain dependency for grader, subprocess plumbing |

**Decision: `javalang` first, with a `JavaAstParser` Protocol so swapping
to JavaParser later is a single-file change.** The S1 sample set is Spring
AI / LangChain4j / MCP — all Java 17 idiomatic — so `javalang` covers it.

### 3. Embedding model: local `sentence-transformers/all-MiniLM-L6-v2`

`project_plan.md` § 4 currently mentions `text-embedding-3-small` (OpenAI).

| Option | Pro | Con |
|---|---|---|
| OpenAI `text-embedding-3-small` | Slightly better recall on diverse text | Requires `OPENAI_API_KEY` for grader, adds cross-provider failure modes |
| **`all-MiniLM-L6-v2` via `sentence-transformers`** | Zero extra key, deterministic, ~80MB one-time download | Slightly worse on out-of-domain text |

**Decision: local.** The corpus is ~30 agent patterns + ~10 OWASP entries
— a domain so small that a strong embedding model is overkill. Eliminating
the second API key dependency is worth more than the marginal recall gain.

### 4. Retrieval index: numpy + cosine, no FAISS

40 entries × 384 dimensions = a 40×384 float32 matrix (~60 KB). FAISS adds
a heavy dependency and complicates the build for a corpus that fits in L2
cache. **Decision: in-memory `numpy.ndarray`, cosine similarity by dot
product on L2-normalized vectors.** ~30 lines of code, no extra dep.

If the corpus ever grows past ~5k entries we'll revisit, but that won't
happen during this course.

### 5. CLI framework: `typer`

| Option | Pro | Con |
|---|---|---|
| `argparse` (stdlib) | Zero deps | Verbose, separate parsing/dispatch glue |
| `click` | Mature, popular | Decorator-heavy boilerplate |
| **`typer`** | Type hints → CLI flags directly, ~20 lines for the whole CLI | One small dep (already transitively pulled by FastAPI) |

**Decision: `typer`.** Add to `engine/pyproject.toml` dependencies.

### 6. Persistence: none

The pipeline is stateless. The retrieval index is built once at startup
from `engine/configs/`. Eval results land as JSON files in `engine/eval/results/`.
**No SQLite, no SQLAlchemy, no DB.** This is a hard "no" — if a future
feature needs a DB, that triggers an ADR, not a quiet `pip install sqlalchemy`.

### 7. LLM call boundary: only Generator and Judge

| Stage | Uses LLM? | Role from `agents.yaml` |
|---|---|---|
| Analyzer | No | — |
| Retriever | No (embeddings happen at startup, not per-request) | — |
| Generator | Yes | `test_synthesizer` |
| Validator | No | — |
| Aggregator | No | — |
| Baseline endpoint | Yes | `baseline` |
| Eval refusal-correctness check | Yes | `judge` |

**Decision: locked as above.** No LLM in non-LLM stages without an explicit
ADR. This keeps cost predictable and the analyzer cacheable.

---

## Stage contracts

These dataclasses are the typed contracts between stages. They live in
`engine/src/agenttest/contracts.py` and are imported by every stage. No
stage may invent its own RiskSite shape.

```python
# engine/src/agenttest/contracts.py
from dataclasses import dataclass, field
from typing import Literal

OwaspRiskId = str  # e.g., "LLM01_Prompt_Injection", "Agentic_Multi_Tenant"

SiteKind = Literal[
    "prompt_assembly",      # builds a PromptTemplate from user input
    "tool_handler",         # @Tool method or LangChain4j tool implementation
    "mcp_endpoint",         # MCP server tool registration / handler
    "tenant_boundary",      # privileged op that takes tenantId
    "retry_config",         # Resilience4j or similar retry/CB config
]


@dataclass(frozen=True)
class RiskSite:
    """Output of analyzer; input to retriever."""
    file_path: str
    line_start: int
    line_end: int
    site_kind: SiteKind
    method_name: str
    candidate_risks: list[OwaspRiskId]   # ordered by analyzer's confidence
    snippet: str                          # raw source for the site


@dataclass(frozen=True)
class OwaspEntry:
    risk_id: OwaspRiskId
    title: str
    description: str
    exemplar_java: str
    exemplar_test: str


@dataclass(frozen=True)
class PatternExample:
    pattern_id: str          # e.g., "spring_ai/prompt_template_basic"
    description: str
    java_source: str
    similarity: float        # cosine, 0–1


@dataclass(frozen=True)
class Grounding:
    """Output of retriever; input to generator. One per (site, candidate_risk) pair."""
    site: RiskSite
    risk_id: OwaspRiskId
    owasp_entry: OwaspEntry
    pattern_examples: list[PatternExample]   # top-3, ordered


@dataclass(frozen=True)
class GeneratedTest:
    """Output of generator. Mirrors the JSON schema the LLM returns."""
    risk_id: OwaspRiskId
    target_lines: tuple[int, int]
    test_method_source: str
    assertion_rationale: str
    refused: bool = False
    refusal_reason: str | None = None


@dataclass(frozen=True)
class ValidatedTest:
    """Output of validator. Surviving tests only."""
    test: GeneratedTest
    compiled_class_bytes: bytes      # for the aggregator's classpath check
    runs_clean_on_clean_input: bool  # always True after validator gate


@dataclass(frozen=True)
class TestClassEmission:
    """Output of aggregator; final pipeline output."""
    target_class_name: str
    output_path: str
    java_source: str
    risks_covered: list[OwaspRiskId]
    refused_sites: list[tuple[RiskSite, str]]  # (site, reason) for refusals
```

The fields are deliberate — every one is consumed by at least one downstream
stage or the eval harness. No "future use" placeholders.

---

## Module layout (`engine/src/agenttest/`)

```
agenttest/
├── __init__.py
├── main.py                 # FastAPI app + lifespan (already exists)
├── config.py               # pydantic-settings (already exists)
├── contracts.py            # dataclasses above (NEW, S1)
├── pipeline.py             # the shared async pipeline function (NEW, S1)
├── cli.py                  # typer CLI entry point (NEW, S1)
│
├── http/                   # FastAPI routes (already exists)
│   ├── __init__.py
│   └── routes.py           # add /generate and /generate/baseline (S2-S3)
│
├── agents/                 # Per-role Claude clients (already exists, done)
│   └── ...
│
├── adapters/               # External integrations (already exists)
│   └── registry.py         # ProviderRegistry, done
│
├── analyzer/               # NEW, S1
│   ├── __init__.py
│   ├── ast_parser.py       # JavaAstParser Protocol + javalang impl
│   └── identify.py         # rules: prompt_assembly, tool_handler, …
│
├── retrieval/              # NEW, S2
│   ├── __init__.py
│   ├── index.py            # numpy cosine index (build once at startup)
│   ├── embed.py            # sentence-transformers wrapper
│   ├── owasp.py            # load configs/owasp.yaml
│   └── patterns.py         # load configs/patterns/**/*.yaml
│
├── generator/              # NEW, S2
│   ├── __init__.py
│   ├── prompt.py           # system + user prompt assembly
│   └── synthesize.py       # call test_synthesizer, parse JSON, emit GeneratedTest
│
├── validator/              # NEW, S2
│   ├── __init__.py
│   ├── parse.py            # javalang parse-check on test_method_source
│   ├── run.py              # subprocess to engine/eval/runner-helper TestRunner
│   │                       # (compile + run-on-clean in one shot —
│   │                       # supersedes the planned compile.py + runtime.py
│   │                       # split, since the runner-helper does both)
│   └── gate.py             # chains parse → run, returns ValidatedTest|None
│
└── aggregator/             # NEW, S2
    ├── __init__.py
    └── emit.py             # combine surviving methods into one .java
```

---

## Eval harness layout (`engine/eval/`)

```
engine/eval/
├── __init__.py
├── runner.py               # main entry: runs ablation matrix, writes results/
├── samples/
│   ├── spring_ai/
│   │   ├── prompt_assembler_clean.java
│   │   └── prompt_assembler_clean.meta.yaml    # injectable risks + expected fail location
│   ├── langchain4j/
│   ├── mcp/
│   ├── multi_tenant/
│   └── resilience/
├── injections/
│   ├── __init__.py
│   ├── base.py             # Injection ABC: apply(java_src) -> patched_src
│   ├── llm01_remove_sanitization.py
│   ├── llm02_log_request.py
│   ├── llm06_tool_description_mismatch.py
│   ├── agentic_drop_tenant_check.py
│   └── resilience_unbounded_retry.py
├── ablation.py             # the 5 configurations from project_plan.md § 5
└── results/                # gitignored, per-run JSON dumps
    └── .gitkeep
```

The `*.meta.yaml` next to each Java sample carries:

```yaml
sample_id: spring_ai/prompt_assembler_clean
description: "Spring AI PromptTemplate assembler that interpolates user query"
target_class: RestaurantPromptAssembler
applicable_injections:
  - llm01_remove_sanitization
  - llm02_log_request
expected_fail_locations:
  llm01_remove_sanitization:
    method: assemble
    line_range: [12, 18]
```

This is the eval ground truth — version-controlled, diff-reviewable, and
referenced directly by the runner.

---

## Cascading edits owed to `docs/project_plan.md`

These follow from the decisions above. Apply once you confirm.

| § | Current text | Should become |
|---|---|---|
| § 4 RAG | "embedded index (`text-embedding-3-small`)" | "embedded index (`sentence-transformers/all-MiniLM-L6-v2`, local; ~80 MB one-time download, no extra API key)" |
| § 4 RAG | "Per risk site, retrieve top-3 from the pattern library" | (unchanged — retrieval count stays top-3) |
| § 7 Privacy | "the surrounding-context snippet is also sent to **OpenAI** for embedding via `text-embedding-3-small`" | Drop this clause entirely. Embeddings are local. |
| § 7 API keys | "`OPENAI_API_KEY` (only required if RAG is enabled — disabled by default for the smoke-test example)" | Drop this bullet. Only `ANTHROPIC_API_KEY` is needed. |

The `.zh.md` mirror gets the same edits.

---

## Open questions explicitly deferred

These are real questions but **don't block S1**. We'll punt them and revisit
when the data forces a decision.

1. **Generator retry policy on JSON-parse failure.** If the Sonnet response
   isn't valid JSON, do we retry once with a "fix the JSON" prompt or just
   refuse? Defer to S2 once we see real failure rates.
2. **Aggregator import resolution.** When two generated methods need
   conflicting `import` aliases, who wins? Defer to S2 — likely won't
   happen with JUnit 5 + Mockito's narrow API surface.
3. **Per-tenant rate-limiting in the FastAPI engine.** Not needed for the
   course project (single user). Flag if we ever multi-tenant the engine.
4. **OWASP catalog auto-update.** OWASP publishes revisions. We pin a
   snapshot in `engine/configs/owasp.yaml` and update manually. Auto-update
   is post-course concern.

---

## S2 retrospective

S2 implemented the LLM01 end-to-end path. Two non-obvious findings
surfaced during prompt iteration and bind future S3+ work:

1. **`target_class_fqn` must be threaded into the generator prompt
   explicitly.** Sonnet defaults to inventing a plausible-but-wrong
   package when the FQN isn't in the prompt body, which breaks
   `new <Target>()` once the test is wrapped in the target's package.
   The `Grounding`/prompt assembly must always carry the resolved
   FQN, not just the bare class name.

2. **Sample `sanitize()` (or equivalent guard) coverage must match
   the OWASP entry's `invariant_to_assert` payload list.** S2's
   first iteration shipped samples whose sanitize() handled only
   one of the LLM01 breakout payloads; the generator emitted tests
   asserting *every* payload, so recall was capped by the sample's
   own guard, not the system. Lesson: when authoring a clean sample,
   walk the OWASP entry's invariant_to_assert payload set and ensure
   the clean code defends against **all** of them. S3 sample-author
   work (LLM06 / LLM02) is bound by this rule.

---

## What S1 actually builds (driven by this doc)

Concrete S1 deliverable, in dependency order:

1. `contracts.py` — all the dataclasses above
2. `analyzer/ast_parser.py` + `analyzer/identify.py` with **one** rule
   (prompt_assembly → LLM01 candidate). Returns `list[RiskSite]`.
3. `pipeline.py` — async function that runs analyzer only for now and
   emits a `TestClassEmission` with `refused_sites` populated and
   `java_source = "// no tests yet — generator stage TBD"`.
4. `cli.py` — typer CLI that calls `pipeline.run()` in-process, prints
   progress, writes the (placeholder) Java file.
5. End-to-end smoke: `python -m agenttest.cli generate sample.java`
   produces a placeholder test class file. No LLM call yet.

S2 fills in retrieval, generator, validator, aggregator. S3 wires the
HTTP path and the baseline endpoint.
