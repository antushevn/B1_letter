"""Exercise checking and history-driven topic recommendations.

Recommendations are the point of this module: every letter/picture attempt
tags its errors with a category from storage.ERROR_CATEGORIES, and every
curriculum topic declares which categories it trains. Topics whose categories
match the learner's most frequent errors float to the top; topics the learner
has already mastered in drills sink to the bottom.
"""

import random

from ..common import storage
from .content import all_exercises, load_topics

# A topic counts as mastered once drill accuracy reaches this level over at
# least MASTERY_MIN_ANSWERED answered exercises (sessions are 8 exercises, so
# mastery needs at least two good sessions).
MASTERY_ACCURACY = 0.9
MASTERY_MIN_ANSWERED = 12

# Exercises per drill session, sampled randomly from core + pool so that
# repeating a topic serves fresh questions instead of memorised answers.
SESSION_SIZE = 8


def sample_session(topic: dict) -> list[dict]:
    pool = all_exercises(topic)
    return random.sample(pool, min(SESSION_SIZE, len(pool)))


def normalise_gap(answer: str) -> str:
    return " ".join(answer.strip().lower().replace("!", " ").replace("?", " ")
                    .replace(".", " ").replace(",", " ").split())


def check_exercise(exercise: dict, answer) -> bool:
    """Deterministic check. `answer` is an option index for "mc", a string for
    "gap". Gap answers are forgiving: punctuation is ignored, and extra words
    are fine as long as they are copied from the sentence itself (a learner
    typing "den Mann" where the gap is only "den" is still correct)."""
    if exercise["type"] == "mc":
        return answer == exercise["answer"]

    given = normalise_gap(str(answer))
    prompt_words = set(normalise_gap(exercise["prompt"]).split())
    for accepted in exercise["accepted"]:
        accepted = normalise_gap(accepted)
        if given == accepted:
            return True
        # Strip surrounding words the learner copied from the prompt and see
        # if the accepted answer is what remains, in order.
        extra = [w for w in given.split() if w not in prompt_words]
        if " ".join(extra) == accepted:
            return True
    return False


def grade_session(topic: dict, exercises: list[dict], answers: list) -> dict:
    """Grade one drill session and build the history record."""
    results = [check_exercise(ex, ans) for ex, ans in zip(exercises, answers)]
    correct = sum(results)
    total = len(results)
    # Each wrong answer counts against every category the topic trains, so the
    # weakness signal lands in the same taxonomy the letter/picture graders use.
    wrong_categories = [
        cat for ok in results if not ok for cat in topic.get("categories", ["other"])
    ]
    return {
        "results": results,
        "correct": correct,
        "total": total,
        "record": {
            "topic_id": topic["id"],
            "correct": correct,
            "total": total,
            "wrong_categories": wrong_categories,
        },
    }


def topic_mastery(stats: dict[str, dict], topic_id: str) -> dict:
    """Mastery info for one topic from grammar_topic_stats output."""
    s = stats.get(topic_id, {"attempts": 0, "answered": 0, "correct": 0, "accuracy": 0.0})
    mastered = (
        s["answered"] >= MASTERY_MIN_ANSWERED and s["accuracy"] >= MASTERY_ACCURACY
    )
    return {**s, "mastered": mastered}


def recommend_topics(all_attempts: list[dict]) -> list[dict]:
    """All curriculum topics ordered by how urgently they need practice.

    Returns [{topic, weakness, mastery, recommended}] sorted most-urgent first.
    `weakness` = how often the learner's letter/picture/grammar errors hit the
    topic's categories; mastered topics always sort behind unmastered ones.
    """
    error_counts = storage.error_category_counts(all_attempts)
    grammar_attempts = [a for a in all_attempts if a.get("module") == "grammar"]
    stats = storage.grammar_topic_stats(grammar_attempts)

    ranked = []
    for topic in load_topics():
        weakness = sum(error_counts.get(cat, 0) for cat in topic.get("categories", []))
        mastery = topic_mastery(stats, topic["id"])
        ranked.append({"topic": topic, "weakness": weakness, "mastery": mastery})

    ranked.sort(key=lambda r: (r["mastery"]["mastered"], -r["weakness"]))

    # Flag the top picks that actually have an error signal behind them.
    recommended_left = 3
    for r in ranked:
        r["recommended"] = (
            not r["mastery"]["mastered"] and r["weakness"] > 0 and recommended_left > 0
        )
        if r["recommended"]:
            recommended_left -= 1
    return ranked
