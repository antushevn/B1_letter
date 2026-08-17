"""Persistence + aggregation for graded practice attempts, all modules.

Two interchangeable backends, chosen at runtime by save_attempt/load_attempts:

- **MongoDB** (when MONGO_URI is set, via local .env or Streamlit secrets) —
  the durable backend. History lives in an external Atlas cluster, so it
  survives the ephemeral hosted filesystem and app restarts. This is what the
  deployed app uses.
- **JSON-lines file** at data/history.jsonl (the fallback when no MONGO_URI) —
  one attempt per line, no external services. Keeps local dev and the offline
  content scripts working with zero extra setup.

Every record carries a "module" field: "letter", "picture", or "grammar".
Legacy file records written before modules existed have no field and count as
"letter"; Mongo records always carry one.

The stats page still offers export/import (JSON-lines) — handy for backups and
for seeding a fresh Mongo collection from a previously exported file.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# storage may be imported before llm.py, so load .env here too (idempotent).
load_dotenv()

HISTORY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "history.jsonl"

MODULES = ("letter", "picture", "grammar")

# ── Durable backend (optional MongoDB) ───────────────────────────────────────
# All attempts land in one collection; the "module" field distinguishes them.
# Override the database name with MONGO_DB if you want to isolate environments
# (e.g. a separate db for local experiments vs. the deployed app).
_MONGO_DB_NAME = os.environ.get("MONGO_DB", "b1_trainer")
_MONGO_COLLECTION = "attempts"

_collection = None          # cached pymongo Collection, or None for file backend
_collection_resolved = False


def _mongo_uri() -> str | None:
    """Connection string from the environment (.env) or Streamlit secrets."""
    uri = os.environ.get("MONGO_URI")
    if uri:
        return uri
    try:
        import streamlit as st

        if "MONGO_URI" in st.secrets:
            return st.secrets["MONGO_URI"]
    except Exception:
        # Not running under Streamlit (offline scripts) — env alone rules.
        pass
    return None


def _get_collection():
    """Return the MongoDB attempts collection, or None to use the file backend.

    Resolved once and cached. Any failure — no URI, pymongo missing, cluster
    unreachable — falls back to the local file so the app still runs.
    """
    global _collection, _collection_resolved
    if _collection_resolved:
        return _collection
    _collection_resolved = True

    uri = _mongo_uri()
    if not uri:
        return None
    try:
        from pymongo import MongoClient

        mongo_client = MongoClient(
            uri, serverSelectionTimeoutMS=5000, appname="b1-trainer"
        )
        mongo_client.admin.command("ping")  # fail fast if unreachable
        coll = mongo_client[_MONGO_DB_NAME][_MONGO_COLLECTION]
        coll.create_index([("timestamp", 1), ("module", 1)])
        _collection = coll
    except Exception:
        _collection = None
    return _collection


def backend_name() -> str:
    """'mongodb' when the durable backend is active, else 'file'. For the UI."""
    return "mongodb" if _get_collection() is not None else "file"

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
    """Persist one graded attempt to the active backend (Mongo or file)."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "module": module,
        **record,
    }
    coll = _get_collection()
    if coll is not None:
        coll.insert_one(dict(record))  # copy: insert_one adds an _id in place
        return
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_attempts(module: str | None = None) -> list[dict]:
    """Attempts in chronological (timestamp) order.

    With `module` given, only that module's attempts are returned. Malformed
    file lines are skipped; the Mongo `_id` field is projected out.
    """
    coll = _get_collection()
    if coll is not None:
        query = {} if module is None else {"module": module}
        return list(coll.find(query, {"_id": 0}).sort("timestamp", 1))

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
    """History as JSON-lines for a download button (empty if no history yet).

    Reads through the active backend, so it works with Mongo or the file.
    """
    attempts = load_attempts()
    if not attempts:
        return b""
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in attempts)
    return (body + "\n").encode("utf-8")


def _parse_export(data: bytes) -> list[dict]:
    records = []
    for line in data.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("timestamp"):
            record.pop("_id", None)  # never carry a foreign Mongo id across
            records.append(record)
    return records


def import_bytes(data: bytes) -> int:
    """Merge an uploaded JSON-lines export into the active backend.

    Records are deduplicated on (timestamp, module). Returns the number of
    records after the merge; raises ValueError if the upload has none valid.
    """
    imported = _parse_export(data)
    if not imported:
        raise ValueError("no valid records in upload")

    coll = _get_collection()
    if coll is not None:
        existing = {
            (a.get("timestamp"), a.get("module", "letter")) for a in load_attempts()
        }
        fresh = []
        for record in imported:
            key = (record.get("timestamp"), record.get("module", "letter"))
            if key in existing:
                continue
            existing.add(key)
            fresh.append(record)
        if fresh:
            coll.insert_many([dict(r) for r in fresh])
        return coll.count_documents({})

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
