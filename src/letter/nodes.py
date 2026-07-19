import json
import random
from functools import lru_cache
from pathlib import Path

from langgraph.types import interrupt

from ..common import storage
from ..common.llm import (
    CHECK_MODEL,
    FEEDBACK_LANGUAGES,
    GRADING_EFFORT,
    TOPIC_MODEL,
    client,
    extract_json,
)
from .prompts import CHECK_SYSTEM, CHECK_USER_TEMPLATE, TOPIC_SYSTEM, TOPIC_USER
from .state import PracticeState

# Pre-generated pool of German tasks (built offline via scripts/build_topic_pool.py).
_TOPIC_POOL_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "topics.json"


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
    response = client.messages.create(
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
    # Sonnet thinks adaptively by default and thinking shares max_tokens with
    # the answer, hence the higher cap than the old Haiku setup needed.
    response = client.messages.create(
        model=CHECK_MODEL,
        max_tokens=4096,
        output_config={"effort": GRADING_EFFORT},
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
    data = json.loads(extract_json(response.content[0].text))

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
    storage.save_attempt(
        {
            "language": state.get("language", "en"),
            "topic": state.get("topic", ""),
            "user_letter": state.get("user_letter", ""),
            **result,
        },
        module="letter",
    )

    return result
