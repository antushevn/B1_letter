"""Local persistence + aggregation for graded practice attempts.

Single-user local app, so history is a simple append-only JSON-lines file
(one attempt per line) at data/history.jsonl. No external dependencies.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "history.jsonl"

# Fixed error taxonomy — the model tags every error with one of these keys so
# statistics can group errors by type ("weak areas"). Keys are stable/English;
# the UI maps them to localised labels.
ERROR_CATEGORIES = (
    "article",          # wrong/missing article (der/die/das, einen/einem)
    "case",             # wrong case (Dativ vs Akkusativ, …)
    "word_order",       # verb not in 2nd position / subordinate-clause order
    "separable_verb",   # separable verb not split correctly
    "preposition",      # missing/wrong preposition
    "verb_conjugation", # wrong person/number/tense
    "register",         # du/Sie register error
    "spelling",         # spelling mistake
    "greeting",         # missing/inappropriate greeting or sign-off
    "other",            # anything not covered above
)

# How many recent attempts must all be "Pass" for the exam-readiness badge.
READINESS_WINDOW = 5


def save_attempt(record: dict) -> None:
    """Append one graded attempt to the history file."""
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **record}
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_attempts() -> list[dict]:
    """Return all attempts in chronological (write) order; skip malformed lines."""
    if not HISTORY_PATH.exists():
        return []
    attempts = []
    for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            attempts.append(json.loads(line))
        except ValueError:
            continue
    return attempts


def current_pass_streak(attempts: list[dict]) -> int:
    """Number of consecutive 'Pass' attempts counting back from the latest."""
    streak = 0
    for a in reversed(attempts):
        if a.get("score") == "Pass":
            streak += 1
        else:
            break
    return streak


def compute_readiness(attempts: list[dict], window: int = READINESS_WINDOW) -> dict:
    """Exam-readiness = the last `window` attempts all scored 'Pass'."""
    recent = attempts[-window:]
    recent_passes = sum(1 for a in recent if a.get("score") == "Pass")
    ready = len(recent) >= window and recent_passes == window
    return {
        "ready": ready,
        "window": window,
        "considered": len(recent),
        "recent_passes": recent_passes,
    }


def error_category_counts(attempts: list[dict]) -> dict[str, int]:
    """Total count per error category across all attempts, most frequent first."""
    counts: dict[str, int] = {}
    for a in attempts:
        for err in a.get("errors", []) or []:
            cat = err.get("category") or "other"
            if cat not in ERROR_CATEGORIES:
                cat = "other"
            counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


def summary(attempts: list[dict]) -> dict:
    """Headline numbers for the stats view."""
    total = len(attempts)
    passes = sum(1 for a in attempts if a.get("score") == "Pass")
    return {
        "total": total,
        "passes": passes,
        "pass_rate": (passes / total) if total else 0.0,
        "streak": current_pass_streak(attempts),
        **compute_readiness(attempts),
    }
