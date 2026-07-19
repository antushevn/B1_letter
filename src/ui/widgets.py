"""Small render helpers shared by the letter and picture pages."""

import streamlit as st
import streamlit.components.v1 as components

from ..common import storage
from .i18n import GRADE_COLOUR, SCORE_COLOUR


def disable_spellcheck():
    """Turn off the browser's native spell-/grammar-check on textareas so the
    learner writes unaided (feedback is given only after submission)."""
    components.html(
        """
        <script>
        const doc = window.parent.document;
        doc.querySelectorAll('textarea').forEach((t) => {
            t.setAttribute('spellcheck', 'false');
            t.setAttribute('autocorrect', 'off');
            t.setAttribute('autocapitalize', 'off');
            t.setAttribute('autocomplete', 'off');
        });
        </script>
        """,
        height=0,
    )


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
        for i, err in enumerate(errors, 1):
            with st.expander(f"{i}. „{err.get('original', '')}\""):
                st.markdown(f"**{T['correction']}:** {err.get('correction', '')}")
                st.markdown(f"**{T['explanation']}:** {err.get('explanation', '')}")
    else:
        st.success(T["no_errors"])
