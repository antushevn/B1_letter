import json

from anthropic import Anthropic
from dotenv import load_dotenv
from langgraph.types import interrupt

from .prompts import CHECK_SYSTEM, CHECK_USER_TEMPLATE, TOPIC_SYSTEM, TOPIC_USER
from .state import PracticeState

load_dotenv()

_client = Anthropic()
MODEL = "claude-haiku-4-5-20251001"


def generate_topic(state: PracticeState) -> dict:
    response = _client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=TOPIC_SYSTEM,
        messages=[{"role": "user", "content": TOPIC_USER}],
    )
    return {"topic": response.content[0].text.strip()}


def await_letter(state: PracticeState) -> dict:
    user_letter = interrupt("awaiting_letter")
    return {"user_letter": user_letter}


def check_letter(state: PracticeState) -> dict:
    response = _client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=CHECK_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": CHECK_USER_TEMPLATE.format(
                    topic=state["topic"],
                    letter=state["user_letter"],
                ),
            }
        ],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    data = json.loads(raw)
    return {
        "feedback": data.get("feedback", ""),
        "score": data.get("score", ""),
        "criterion_scores": data.get("criterion_scores", {}),
        "positives": data.get("positives", []),
        "missing_points": data.get("missing_points", []),
        "errors": data.get("errors", []),
    }
