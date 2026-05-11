"""Open Org theme vocabulary helpers.

The vocabulary itself lives in ``data/themes.json`` so it can be diffed,
versioned, and consumed by non-Python tools (e.g. the discovery UI).
This module provides cached Python-friendly access.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_THEMES_PATH = Path(__file__).resolve().parent / "data" / "themes.json"


@lru_cache(maxsize=1)
def load_themes() -> list[dict]:
    """Return the full theme list (key, label, description) from disk."""
    with _THEMES_PATH.open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def theme_keys() -> frozenset[str]:
    """Return all valid theme keys as a frozenset for fast membership checks."""
    return frozenset(t["key"] for t in load_themes())


def is_valid_theme(key: str) -> bool:
    """True if ``key`` is in the controlled vocabulary."""
    return key in theme_keys()
