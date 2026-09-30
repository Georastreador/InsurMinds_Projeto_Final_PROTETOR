"""LLM-facing contract derived from the canonical PolicySchema.

The Pydantic model stays the single source of truth. This module only adapts its
JSON Schema to the subset accepted by provider strict structured outputs:
every object closed (additionalProperties=false), every property listed in
`required` (optional values are expressed as `null` in anyOf), and validation-only
keywords removed. Local validation by A4 still applies the full Pydantic rules.
"""
from __future__ import annotations
import copy
from typing import Any

# Identity fields are pipeline facts assigned by A3, never requested from the LLM.
PIPELINE_OWNED_FIELDS = ("document_id", "source_file")

# Keywords that strict mode rejects or that only A4 needs to enforce.
# `format` is removed because forcing the date shape made the model garble DD/MM/YYYY dates;
# A4 normalizes and validates dates instead.
_STRIPPED_KEYWORDS = ("default", "title", "pattern", "format", "minLength", "maxLength", "minimum", "maximum")


def _sanitize(node: Any) -> Any:
    if isinstance(node, list):
        return [_sanitize(x) for x in node]
    if not isinstance(node, dict):
        return node
    out = {k: v for k, v in node.items() if k not in _STRIPPED_KEYWORDS}
    if "properties" in out:
        out["properties"] = {name: _sanitize(schema) for name, schema in out["properties"].items()}
        out["required"] = list(out["properties"])
        out["additionalProperties"] = False
    for key in ("items", "anyOf", "allOf", "oneOf"):
        if key in out:
            out[key] = _sanitize(out[key])
    if "$defs" in out:
        out["$defs"] = {name: _sanitize(schema) for name, schema in out["$defs"].items()}
    return out


def strict_policy_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a strict-mode JSON Schema for A3 from PolicySchema.model_json_schema()."""
    schema = copy.deepcopy(schema)
    for field in PIPELINE_OWNED_FIELDS:
        schema.get("properties", {}).pop(field, None)
    return _sanitize(schema)
