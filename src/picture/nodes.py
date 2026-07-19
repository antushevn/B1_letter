import base64
import json
import random
from functools import lru_cache
from pathlib import Path

from langgraph.types import interrupt

from ..common import storage
from ..common.llm import FEEDBACK_LANGUAGES, PICTURE_MODEL, client, extract_json
from .prompts import DESCRIBE_SYSTEM, DESCRIBE_USER_TEMPLATE
from .state import PictureState

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
PICTURES_DIR = DATA_DIR / "pictures"
MANIFEST_PATH = DATA_DIR / "pictures.json"


@lru_cache(maxsize=1)
def load_manifest() -> tuple[dict, ...]:
    try:
        entries = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return ()
    return tuple(
        e for e in entries if (PICTURES_DIR / e.get("file", "")).exists()
    )


def get_entry(picture_id: str) -> dict | None:
    return next((e for e in load_manifest() if e["id"] == picture_id), None)


def picture_path(entry: dict) -> Path:
    return PICTURES_DIR / entry["file"]


def pick_picture(state: PictureState) -> dict:
    pool = load_manifest()
    if not pool:
        raise RuntimeError(
            "Picture pool is empty — run scripts/build_picture_pool.py first."
        )
    entry = random.choice(pool)
    return {
        "picture_id": entry["id"],
        "picture_file": entry["file"],
        "scene": entry["scene"],
    }


def await_description(state: PictureState) -> dict:
    description = interrupt("awaiting_description")
    return {"description": description}


def check_description(state: PictureState) -> dict:
    feedback_language = FEEDBACK_LANGUAGES.get(state.get("language", "en"), "English")
    system = DESCRIBE_SYSTEM.replace("{feedback_language}", feedback_language)

    image_data = base64.standard_b64encode(
        (PICTURES_DIR / state["picture_file"]).read_bytes()
    ).decode("utf-8")

    response = client.messages.create(
        model=PICTURE_MODEL,
        max_tokens=2048,
        system=system,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": DESCRIBE_USER_TEMPLATE.format(
                            scene=state["scene"],
                            description=state["description"],
                            feedback_language=feedback_language,
                        ),
                    },
                ],
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
        "missing_steps": data.get("missing_steps", []),
        "errors": errors,
    }

    # Persist for statistics — picture errors feed the same weak-area taxonomy
    # that drives grammar-topic recommendations.
    storage.save_attempt(
        {
            "language": state.get("language", "en"),
            "picture_id": state.get("picture_id", ""),
            "scene": state.get("scene", ""),
            "description": state.get("description", ""),
            **result,
        },
        module="picture",
    )

    return result
