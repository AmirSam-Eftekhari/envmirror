"""Machine-readable comparison output."""

from __future__ import annotations

import json

from ..models.comparison import ComparisonResult


def comparison_to_json(result: ComparisonResult) -> str:
    """Deterministic JSON: sorted keys, 2-space indent, trailing newline."""
    return json.dumps(result.model_dump(mode="json"), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
