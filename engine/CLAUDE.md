# CLAUDE.md — `engine/`

FastAPI engine conventions for AgentTest. Read `../CLAUDE.md` first for
project-level rules.

## Build & Test

```bash
cd engine
pip install -e ".[dev]"            # install with dev deps (pytest)
uvicorn agenttest.main:app --reload --port 8000
pytest                              # all tests
pytest tests/test_agents.py -v      # single test file
pytest -k "factory"                 # filter by name
pytest -m "not integration"         # skip real-LLM-call tests
```

## CRITICAL — async contract

- **Everything in the request path is `async def`.** FastAPI routes,
  pipeline stages, adapter calls — all async.
- **No sync I/O in async code.** No `requests.get`, no `time.sleep`, no
  `urllib.request`. The `detect-blocking-calls.sh` hook will warn you.
  Use `httpx.AsyncClient` and `asyncio.sleep`.
- **Exception**: pytest test functions and CLI scripts can be sync.
  Anything imported into the FastAPI app must not block.
- **Anthropic SDK**: use `AsyncAnthropic`, never `Anthropic`. Already
  wired in `agents/factory.py` via the `ProviderRegistry`.
- **PIT / Maven / Java subprocesses**: use `asyncio.create_subprocess_exec`,
  never `subprocess.run`, when called from request-path code. Synchronous
  subprocess calls are OK in the eval harness CLI (which is sync).

## Layered Architecture (do not collapse layers)

```
http/           ← FastAPI routes + SSE serialization. NO business logic.
agents/         ← Per-role Claude clients (built on ProviderRegistry).
adapters/       ← External integrations: ProviderRegistry today;
                  Java toolchain wrappers (PIT, Maven, JavaParser) later.
config.py       ← pydantic-settings, env-driven config.

# To be added during implementation (see docs/project_plan.md § 4):
analyzer/       ← Java AST analysis. Identify risk-relevant patterns
                  (prompt-assembly call sites, tool handler signatures,
                  retry/circuit-breaker boundaries). NO LLM calls here.
retrieval/      ← OWASP risk catalog + agent-pattern library + similar-code
                  retrieval. Returns grounding for the generator.
generator/      ← LLM-driven JUnit test synthesis. Takes analyzer output +
                  retrieval grounding, emits compilable JUnit 5 source.
evaluator/      ← Synthetic injection harness. Takes a clean Java sample,
                  injects an OWASP risk pattern, runs the system, runs the
                  generated tests against both clean and buggy versions,
                  reports recall / precision.
```

A request goes: `http/routes.py → analyzer → retrieval → generator → emit`.
Never skip layers. Domain stages must not import from `http/` or directly
construct `httpx.AsyncClient` — they receive interfaces (Protocols).

## Adding a New Agent Role

1. Add the value to `AgentRole` enum in `agents/role.py`
2. Add the matching block to `configs/agents.yaml` (provider, model,
   max_tokens, temperature, optional `prompt_cache_enabled`)
3. (Optional) Smoke test in `tests/test_agents.py`
4. Restart the server — `AgentClientFactory` builds clients at startup;
   YAML edits do not hot-reload

## Pydantic v2 Conventions

- `BaseModel` for request/response shapes and persisted DTOs
- `BaseSettings` (pydantic-settings) for env-driven config — already in
  `config.py`
- `model_validate` / `model_dump` (NOT v1's `parse_obj` / `dict`)
- `Field(default_factory=list)` for mutable defaults
- Type hints on every public function. Use `dict[str, X]` / `list[X]` /
  `X | None` (Python 3.11+ syntax) — never `Dict` / `List` / `Optional`

## Testing Conventions

- `pytest-asyncio` is configured (`asyncio_mode = "auto"` in
  `pyproject.toml`). Async tests are just `async def test_…`.
- Real Anthropic / OpenAI calls are NOT made in unit tests. The factory
  tests verify wiring (model name, max_tokens) without
  `await client.complete(…)`.
- For tests that need a real LLM, mark with `@pytest.mark.integration`
  and skip in normal runs: `pytest -m "not integration"`.
- `TestClient` handles FastAPI lifespan automatically. The `test_health`
  and `test_agents` tests both work this way.
- **Do not commit fixtures of generated JUnit tests as ground truth.**
  The evaluation ground truth lives in `eval/` as (clean sample,
  injected risk, expected fail location) — generated JUnit code is the
  output under test, not the oracle.

## Pipeline Stage Pattern

Stages take typed input and return typed output from
`agenttest.contracts`. The contracts are frozen dataclasses — stages
must NOT invent their own shapes. Example (the real S1 analyzer):

```python
# engine/src/agenttest/analyzer/identify.py
from dataclasses import dataclass

from agenttest.contracts import RiskSite


@dataclass
class AnalyzerInput:
    java_source: str
    file_path: str


async def identify(
    analyzer_input: AnalyzerInput,
    parser: JavaAstParser | None = None,
) -> list[RiskSite]:
    ...
```

When stubbing a stage that's not implemented yet, fail loudly with a
pointer to the plan, not silent placeholder data:

```python
async def synthesize(grounding: Grounding, ...) -> GeneratedTest:
    raise NotImplementedError(
        "S2 work — see docs/plan/sprint-2.md Step 2 (generator)"
    )
```

## Forbidden

- Catching `Exception` broadly without re-raising (masks bugs)
- `# type: ignore` without an inline justification
- `eval(`, `exec(`, `pickle.loads(` on external input (security)
- Hardcoded paths under `/c/Users/…` or `D:\…` — use `settings.configs_dir`,
  etc.
- Adding a new dependency without updating `pyproject.toml`
- Writing generated JUnit code to disk outside `eval/` or an explicit
  user-provided output path. Generated test code is the deliverable; do
  not silently scatter `.java` files in source trees.
