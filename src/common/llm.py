"""Shared Anthropic client and model tiering for all modules.

The API key comes from the environment (.env locally). On Streamlit Community
Cloud there is no .env — secrets live in st.secrets — so we bridge them into
the environment before the client is created.
"""

import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Model tiering: offline content generation stays on cheap Haiku; the two
# grading paths (the only live calls the app makes) run on Sonnet at low
# effort for noticeably better error analysis at moderate cost.
TOPIC_MODEL = "claude-haiku-4-5-20251001"
CHECK_MODEL = "claude-sonnet-5"
PICTURE_MODEL = "claude-sonnet-5"

# Effort for grading calls: "low" keeps latency/cost down; raise to "medium"
# if grading quality ever feels shallow.
GRADING_EFFORT = "low"

# Feedback language names passed to examiner prompts, keyed by UI language code.
FEEDBACK_LANGUAGES = {"ru": "Russian", "de": "German", "en": "English"}


def _bridge_streamlit_secrets() -> None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    try:
        import streamlit as st

        if "ANTHROPIC_API_KEY" in st.secrets:
            os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        # Not running under Streamlit (e.g. offline scripts) — env alone rules.
        pass


_bridge_streamlit_secrets()

client = Anthropic()


def extract_json(raw: str) -> str:
    """Strip an optional markdown fence from a model response."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return raw
