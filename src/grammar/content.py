"""Loader for the B1 grammar content.

Two layers:
- data/grammar_curriculum.json — hand-written, verified core: lessons, examples
  and 8 exercises per topic. Always ships with the repo.
- data/grammar_pool.json — extended exercise pool, batch-generated offline via
  scripts/build_grammar_pool.py and reviewed by hand. Optional: the module
  works (with a smaller variety) when the file is absent.

The grammar module makes no API calls at runtime.
"""

import json
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CURRICULUM_PATH = _DATA_DIR / "grammar_curriculum.json"
POOL_PATH = _DATA_DIR / "grammar_pool.json"


@lru_cache(maxsize=1)
def load_topics() -> tuple[dict, ...]:
    data = json.loads(CURRICULUM_PATH.read_text(encoding="utf-8"))
    return tuple(data["topics"])


def get_topic(topic_id: str) -> dict | None:
    return next((t for t in load_topics() if t["id"] == topic_id), None)


@lru_cache(maxsize=1)
def load_pool() -> dict[str, tuple[dict, ...]]:
    try:
        data = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
    return {topic_id: tuple(exercises) for topic_id, exercises in data.items()}


def all_exercises(topic: dict) -> list[dict]:
    """Core curriculum exercises plus the extended pool for one topic."""
    return list(topic["exercises"]) + list(load_pool().get(topic["id"], ()))
