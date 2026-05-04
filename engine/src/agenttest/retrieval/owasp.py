"""OWASP catalog loader.

Reads `engine/configs/owasp.yaml` and returns a `dict[OwaspRiskId, OwaspEntry]`
keyed by `risk_id`. The schema is locked in `docs/plan/sprint-2.md`
§ "Locked decision 6"; every entry MUST have all six required fields, and
`invariant_to_assert` is load-bearing for the generator (it threads
verbatim into the user prompt — see `generator/prompt.py`).

Missing-field validation raises `ValueError` naming the field; we don't
silently default. The catalog is small (≤ 10 entries) so per-load
validation cost is negligible.
"""

from pathlib import Path

import yaml

from agenttest.contracts import OwaspEntry, OwaspRiskId

_REQUIRED_FIELDS: tuple[str, ...] = (
    "risk_id",
    "title",
    "description",
    "invariant_to_assert",
    "exemplar_java",
    "exemplar_test",
)


def load_owasp(path: Path) -> dict[OwaspRiskId, OwaspEntry]:
    """Load and validate the OWASP catalog at `path`.

    Returns a dict keyed by `risk_id`. Raises `ValueError` on any of:

      - the YAML root isn't a list
      - any entry isn't a mapping
      - any required field is missing or empty (whitespace-only counts
        as empty for everything except `risk_id` itself)
      - duplicate `risk_id` across entries
    """
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, list):
        raise ValueError(
            f"{path}: expected the YAML root to be a list of OWASP entries, "
            f"got {type(data).__name__}"
        )

    catalog: dict[OwaspRiskId, OwaspEntry] = {}
    for index, raw_entry in enumerate(data):
        if not isinstance(raw_entry, dict):
            raise ValueError(
                f"{path}: entry #{index} must be a mapping, got {type(raw_entry).__name__}"
            )
        for field in _REQUIRED_FIELDS:
            if field not in raw_entry:
                raise ValueError(
                    f"{path}: entry #{index} is missing required field '{field}'"
                )
            value = raw_entry[field]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{path}: entry #{index} field '{field}' must be a non-empty string"
                )

        risk_id: OwaspRiskId = raw_entry["risk_id"].strip()
        if risk_id in catalog:
            raise ValueError(f"{path}: duplicate risk_id '{risk_id}'")

        catalog[risk_id] = OwaspEntry(
            risk_id=risk_id,
            title=raw_entry["title"].strip(),
            description=raw_entry["description"],
            invariant_to_assert=raw_entry["invariant_to_assert"],
            exemplar_java=raw_entry["exemplar_java"],
            exemplar_test=raw_entry["exemplar_test"],
        )

    return catalog
