"""Loader for the letter-writing reference material (Musterbriefe + Redemittel).

Static, hand-authored content in data/reference_letters.json — no API calls.
It backs the "Reference" page: a phrase bank grouped by communicative function
plus model letters (formal + informal) for the common telc B1 letter themes.
"""

import json
from functools import lru_cache
from pathlib import Path

_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "reference_letters.json"
)


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def load_redemittel() -> tuple[dict, ...]:
    """Phrase groups, each: {"function": key, "phrases": [...]}"""
    return tuple(_load().get("redemittel", ()))


def load_letters() -> tuple[dict, ...]:
    """Model letters, each with title/category/register/situation/letter/highlights."""
    return tuple(_load().get("letters", ()))
