"""Small render helpers shared by the letter and picture pages."""

import streamlit as st

from ..common import storage
from .i18n import GRADE_COLOUR, SCORE_COLOUR

# Severity → traffic-light icon for the error list (order = worst first).
_SEVERITY_ICON = {"critical": "🔴", "moderate": "🟡", "minor": "🟢"}


def word_count_line(T, word_count, low, high):
    """Static word-count readout. Updates when Streamlit reruns (e.g. on blur or
    button press), not per keystroke: the earlier live/JS version churned an
    iframe on every rerun and froze the browser, so it was removed."""
    colour = "green" if low <= word_count <= high else "orange"
    st.markdown(f"{T['words']}: :{colour}[**{word_count}**]")


def render_readiness(T, attempts):
    """Exam-readiness badge (green) or the current Pass-streak progress line."""
    s = storage.summary(attempts)
    if s["ready"]:
        st.success(T["readiness_ready"].format(window=s["window"]))
    else:
        st.info(T["readiness_progress"].format(streak=s["streak"], window=s["window"]))
    return s


def render_assessment(T, result, criterion_keys, criterion_labels, missing_label):
    """The common "graded work" block: score badge, feedback, criterion grades,
    missing points, positives, and the error list."""
    score = result.get("score", "")
    colour = SCORE_COLOUR.get(score, "gray")
    score_label = T["score_labels"].get(score, score)
    st.markdown(f"### {T['result']}: :{colour}[**{score_label}**]")
    st.write(result.get("feedback", ""))

    cs = result.get("criterion_scores") or {}
    if cs:
        st.subheader(T["criteria"])
        cols = st.columns(len(criterion_keys))
        for col, key in zip(cols, criterion_keys):
            grade = cs.get(key, "–")
            gc = GRADE_COLOUR.get(grade, "gray")
            col.metric(criterion_labels[key], f":{gc}[**{grade}**]")

    missing = result.get("missing") or []
    if missing:
        st.subheader(missing_label)
        for point in missing:
            st.markdown(f"- {point}")

    positives = result.get("positives") or []
    if positives:
        st.subheader(T["positives"])
        for point in positives:
            st.markdown(f"- {point}")

    errors = result.get("errors") or []
    if errors:
        st.subheader(f"{T['errors']} ({len(errors)})")
        _severity_summary(T, errors)
        # Worst errors first so the learner reads the important ones on top.
        order = {"critical": 0, "moderate": 1, "minor": 2}
        ranked = sorted(
            enumerate(errors, 1),
            key=lambda ie: order.get(ie[1].get("severity", "moderate"), 1),
        )
        for i, err in ranked:
            sev = err.get("severity", "moderate")
            icon = _SEVERITY_ICON.get(sev, "🟡")
            label = T["severity_labels"].get(sev, sev)
            with st.expander(f"{icon} {i}. „{err.get('original', '')}\" — {label}"):
                st.markdown(f"**{T['correction']}:** {err.get('correction', '')}")
                st.markdown(f"**{T['explanation']}:** {err.get('explanation', '')}")
    else:
        st.success(T["no_errors"])


def _severity_summary(T, errors):
    """Extra-info line: total severity weight + a per-level breakdown. The weight
    mirrors telc's 'Primat der Verständlichkeit' — cosmetic slips barely add up,
    a critical error weighs heavily."""
    total = storage.severity_sum(errors)
    parts = []
    for sev in ("critical", "moderate", "minor"):
        n = sum(1 for e in errors if e.get("severity", "moderate") == sev)
        if n:
            parts.append(f"{_SEVERITY_ICON[sev]} {n}")
    breakdown = "  ·  ".join(parts)
    st.caption(f"{T['severity_sum']}: **{total}**  ({breakdown})")
