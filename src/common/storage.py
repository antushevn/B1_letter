"""Local persistence + aggregation for graded practice attempts, all modules.

Single-user local app, so history is a simple append-only JSON-lines file
(one attempt per line) at data/history.jsonl. No external dependencies.

Every record carries a "module" field: "letter", "picture", or "grammar".
Records written before modules existed have no field and count as "letter".

NOTE for hosted deployments (Streamlit Community Cloud): the filesystem is
ephemeral, so the stats page offers export/import of this file. A future
swap to a hosted DB only needs to replace save_attempt/load_attempts.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

HISTORY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "history.jsonl"

MODULES = ("letter", "picture", "grammar")

# Fixed error taxonomy — the model tags every letter/picture error with one of
# these keys so statistics can group errors by type ("weak areas"). Keys are
# stable/English; the UI maps them to localised labels. The grammar curriculum
# tags each topic with the categories it trains, which drives recommendations.
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


def save_attempt(record: dict, module: str = "letter") -> None:
    """Append one graded attempt to the history file."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "module": module,
        **record,
    }
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_attempts(module: str | None = None) -> list[dict]:
    """Attempts in chronological (write) order; skip malformed lines.

    With `module` given, only that module's attempts are returned.
    """
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
    if module is not None:
        attempts = [a for a in attempts if a.get("module", "letter") == module]
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
    """Total count per error category across the given attempts, most frequent
    first. Letter and picture attempts both carry `errors`; grammar attempts
    instead carry `wrong_categories` (categories of exercises answered wrong)."""
    counts: dict[str, int] = {}

    def bump(cat: str) -> None:
        if cat not in ERROR_CATEGORIES:
            cat = "other"
        counts[cat] = counts.get(cat, 0) + 1

    for a in attempts:
        for err in a.get("errors", []) or []:
            bump(err.get("category") or "other")
        for cat in a.get("wrong_categories", []) or []:
            bump(cat)
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


def summary(attempts: list[dict]) -> dict:
    """Headline numbers for the stats view (Pass/Fail-scored modules)."""
    total = len(attempts)
    passes = sum(1 for a in attempts if a.get("score") == "Pass")
    return {
        "total": total,
        "passes": passes,
        "pass_rate": (passes / total) if total else 0.0,
        "streak": current_pass_streak(attempts),
        **compute_readiness(attempts),
    }


def grammar_topic_stats(attempts: list[dict]) -> dict[str, dict]:
    """Per-topic accuracy for grammar attempts: {topic_id: {attempts, answered,
    correct, accuracy}}. Feed grammar-module attempts only."""
    stats: dict[str, dict] = {}
    for a in attempts:
        topic_id = a.get("topic_id")
        if not topic_id:
            continue
        s = stats.setdefault(topic_id, {"attempts": 0, "answered": 0, "correct": 0})
        s["attempts"] += 1
        s["answered"] += a.get("total", 0)
        s["correct"] += a.get("correct", 0)
    for s in stats.values():
        s["accuracy"] = (s["correct"] / s["answered"]) if s["answered"] else 0.0
    return stats


# ── Export / import (survival kit for ephemeral hosted filesystems) ──────────

def export_bytes() -> bytes:
    """Raw history file for a download button (empty if no history yet)."""
    if not HISTORY_PATH.exists():
        return b""
    return HISTORY_PATH.read_bytes()


def import_bytes(data: bytes) -> int:
    """Merge an uploaded history export into the current file.

    Lines are deduplicated on (timestamp, module) and rewritten in timestamp
    order. Returns the number of records after the merge; raises ValueError
    if the upload contains no valid records.
    """
    imported = []
    for line in data.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("timestamp"):
            imported.append(record)
    if not imported:
        raise ValueError("no valid records in upload")

    merged: dict[tuple, dict] = {}
    for record in load_attempts() + imported:
        key = (record.get("timestamp"), record.get("module", "letter"))
        merged[key] = record
    ordered = sorted(merged.values(), key=lambda r: r.get("timestamp") or "")

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("w", encoding="utf-8") as f:
        for record in ordered:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(ordered)
