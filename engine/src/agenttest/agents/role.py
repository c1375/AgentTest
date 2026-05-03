from enum import Enum


class AgentRole(str, Enum):
    """Symbolic names for the LLM roles AgentTest uses.

    Each role has its own model, max_tokens, and temperature, configured
    in `configs/agents.yaml`. The factory iterates this enum and looks
    each entry up in the YAML — adding a role here without an entry in
    YAML (or vice versa) is a wiring bug.

    See `docs/project_plan.md` § 4 for what each role does in the pipeline.
    """

    # Generates one JUnit 5 test method per (risk site, OWASP risk) pair.
    # Largest system prompt (OWASP catalog excerpt + agent-pattern examples
    # + target source) — prompt-cache it.
    TEST_SYNTHESIZER = "test_synthesizer"

    # Single-prompt baseline that the eval harness compares AgentTest
    # against. Same model, same input class, no retrieval, no analyzer,
    # no per-risk loop. See docs/project_plan.md § 4 (Baseline).
    BASELINE = "baseline"

    # Model-as-judge for secondary metrics only (refusal correctness,
    # qualitative spot-check). Primary metrics use objective execution
    # against injected risks — no judge in the primary measurement path.
    JUDGE = "judge"
