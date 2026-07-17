import json
import random
from functools import lru_cache
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv
from langgraph.types import interrupt

from . import storage
from .prompts import CHECK_SYSTEM, CHECK_USER_TEMPLATE, TOPIC_SYSTEM, TOPIC_USER
from .state import PracticeState

load_dotenv()

_client = Anthropic()

# Model tiering: topic generation is an easy task, so keep it on cheap Haiku.
# CHECK_MODEL is the single knob to bump when moving grading to a pricier model.
TOPIC_MODEL = "claude-haiku-4-5-20251001"
CHECK_MODEL = "claude-haiku-4-5-20251001"

# Pre-generated pool of German tasks (built offline via scripts/build_topic_pool.py).
_TOPIC_POOL_PATH = Path(__file__).resolve().parent.parent / "data" / "topics.json"

# Feedback language names passed to the examiner prompt, keyed by UI language code.
FEEDBACK_LANGUAGES = {"ru": "Russian", "de": "German", "en": "English"}


@lru_cache(maxsize=1)
def _load_topic_pool() -> tuple[str, ...]:
    try:
        topics = json.loads(_TOPIC_POOL_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return ()
    return tuple(t for t in topics if isinstance(t, str) and t.strip())


def generate_topic(state: PracticeState) -> dict:
    pool = _load_topic_pool()
    if pool:
        return {"topic": random.choice(pool)}

    # Fallback: no pool yet — generate live on the cheap topic model.
    response = _client.messages.create(
        model=TOPIC_MODEL,
        max_tokens=512,
        system=TOPIC_SYSTEM,
        messages=[{"role": "user", "content": TOPIC_USER}],
    )
    return {"topic": response.content[0].text.strip()}


def await_letter(state: PracticeState) -> dict:
    user_letter = interrupt("awaiting_letter")
    return {"user_letter": user_letter}


def check_letter(state: PracticeState) -> dict:
    feedback_language = FEEDBACK_LANGUAGES.get(state.get("language", "en"), "English")
    system = CHECK_SYSTEM.replace("{feedback_language}", feedback_language)
    response = _client.messages.create(
        model=CHECK_MODEL,
        max_tokens=2048,
        system=system,
        messages=[
            {
                "role": "user",
                "content": CHECK_USER_TEMPLATE.format(
                    topic=state["topic"],
                    letter=state["user_letter"],
                    feedback_language=feedback_language,
                ),
            }
        ],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    data = json.loads(raw)

    errors = []
    for err in data.get("errors", []) or []:
        category = err.get("category", "other")
        if category not in storage.ERROR_CATEGORIES:
            category = "other"
        errors.append({
            "original": err.get("original", ""),
            "correction": err.get("correction", ""),
            "explanation": err.get("explanation", ""),
            "category": category,
        })

    result = {
        "feedback": data.get("feedback", ""),
        "score": data.get("score", ""),
        "criterion_scores": data.get("criterion_scores", {}),
        "positives": data.get("positives", []),
        "missing_points": data.get("missing_points", []),
        "errors": errors,
    }

    # Persist the graded attempt for statistics / exam-readiness tracking.
    storage.save_attempt({
        "language": state.get("language", "en"),
        "topic": state.get("topic", ""),
        "user_letter": state.get("user_letter", ""),
        **result,
    })

    return result
