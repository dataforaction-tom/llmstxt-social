"""JSON Schema validator wrapper for Open Org payloads.

Produces structured error reports keyed by dotted path, suitable for
surfacing in the markdown editor and the API. Schema files live under
``schemas/`` and are loaded on first use, then cached.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator

Kind = Literal["profile", "strategy", "idea"]
_SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"
_SCHEMA_FILES: dict[str, str] = {
    "profile": "org_profile.schema.json",
    "strategy": "org_strategy.schema.json",
    "idea": "org_idea.schema.json",
}


class ValidationError(Exception):
    """Raised when a payload fails JSON Schema validation.

    The ``errors`` attribute carries the structured error list — a list of
    ``{"path": "identity.name", "message": "is required"}`` dicts — so callers
    can surface them in the editor without re-parsing.
    """

    def __init__(self, errors: list[dict[str, str]]) -> None:
        self.errors = errors
        summary = "; ".join(f"{e['path'] or '<root>'}: {e['message']}" for e in errors[:5])
        super().__init__(f"{len(errors)} validation error(s): {summary}")


def _format_path(path_parts) -> str:
    """Convert a jsonschema path deque into a dotted/bracketed string."""
    out = []
    for part in path_parts:
        if isinstance(part, int):
            if out:
                out[-1] = f"{out[-1]}[{part}]"
            else:
                out.append(f"[{part}]")
        else:
            out.append(str(part))
    return ".".join(out)


def validate_iter(payload: Any, *, schema: dict) -> list[dict[str, str]]:
    """Return a list of structured errors for ``payload`` against ``schema``.

    Empty list means valid. Use this when you want to display all errors at once
    (e.g. in the editor) rather than failing on the first.
    """
    validator = Draft202012Validator(schema)
    return [
        {"path": _format_path(err.absolute_path), "message": err.message}
        for err in validator.iter_errors(payload)
    ]


def validate(payload: Any, *, schema: dict) -> None:
    """Validate ``payload`` against ``schema`` or raise :class:`ValidationError`."""
    errors = validate_iter(payload, schema=schema)
    if errors:
        raise ValidationError(errors)


@lru_cache(maxsize=None)
def load_schema(kind: Kind) -> dict:
    """Load and cache an Open Org schema by object kind."""
    if kind not in _SCHEMA_FILES:
        raise ValueError(f"unknown kind: {kind!r} (expected one of {list(_SCHEMA_FILES)})")
    path = _SCHEMAS_DIR / _SCHEMA_FILES[kind]
    with path.open() as f:
        return json.load(f)


def validate_for_kind(payload: Any, *, kind: Kind) -> None:
    """Validate ``payload`` against the Open Org schema for ``kind``."""
    schema = load_schema(kind)
    validate(payload, schema=schema)
