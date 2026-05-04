"""Single-prompt baseline for the AgentTest vs. baseline eval comparison.

The baseline is what a developer using Claude alone would produce: one
prompt asking for JUnit 5 + AssertJ tests targeting OWASP risks, no
analyzer / retrieval / per-risk loop / validator gate. It exists so the
S3 / S5 evaluation can answer "does the structured pipeline beat
single-prompt Claude on the same model + same inputs?"

See `docs/project_plan.md` § 4 (Baseline) for the design rationale and
`docs/plan/sprint-3.md` § "Step 0" for the empirical observations
that shaped the prompt (no Mockito, max_tokens >= 4096, fence wrap).
"""

from .synthesize import BASELINE_PROMPT_TEMPLATE, synthesize_baseline

__all__ = ["BASELINE_PROMPT_TEMPLATE", "synthesize_baseline"]
