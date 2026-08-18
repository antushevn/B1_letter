"""Small render helpers shared by the letter and picture pages."""

import json

import streamlit as st
import streamlit.components.v1 as components

from ..common import storage
from .i18n import GRADE_COLOUR, SCORE_COLOUR

# Word-count colours mirror Streamlit's :green[]/:orange[] text palette.
_WC_IN_RANGE = "#21c354"
_WC_OUT_RANGE = "#ff8700"


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


def word_count_line(T, word_count, low, high):
    """Render the live word-count readout. The number lives in a span that
    live_word_count() updates in the browser; the value passed here is only the
    initial (server-side) count for the first paint."""
    colour = _WC_IN_RANGE if low <= word_count <= high else _WC_OUT_RANGE
    st.markdown(
        f"{T['words']}: <span id='wc-live' "
        f"style='color:{colour};font-weight:700'>{word_count}</span>",
        unsafe_allow_html=True,
    )


def live_word_count(label, low, high):
    """Keep the word counter in sync while the user types. Streamlit only reruns
    a text_area on blur, so the server-rendered number freezes mid-typing. This
    attaches a browser-side 'input' listener that recomputes the count and
    recolours the readout (span#wc-live) with no rerun/round-trip.

    Deliberately never polls indefinitely: it retries the DOM lookup a bounded
    number of times and then gives up, so a missing target (e.g. if the host
    ever strips the span id) can't leave a timer spinning and pinning the tab's
    main thread. The listener is de-duplicated so reruns never stack handlers."""
    components.html(
        f"""
        <script>
        (function () {{
            const doc = window.parent.document;
            const LABEL = {json.dumps(label)};
            const LOW = {low}, HIGH = {high};
            const IN = {json.dumps(_WC_IN_RANGE)}, OUT = {json.dumps(_WC_OUT_RANGE)};
            let tries = 0;
            function bind() {{
                const ta = doc.querySelector('textarea[aria-label=' + JSON.stringify(LABEL) + ']')
                           || doc.querySelector('textarea');
                const out = doc.getElementById('wc-live');
                if (!ta || !out) {{
                    if (tries++ < 30) setTimeout(bind, 150);
                    return;
                }}
                const update = () => {{
                    const n = (ta.value.trim().match(/\\S+/g) || []).length;
                    out.textContent = n;
                    out.style.color = (n >= LOW && n <= HIGH) ? IN : OUT;
                }};
                if (ta._wcUpdate) ta.removeEventListener('input', ta._wcUpdate);
                ta._wcUpdate = update;
                ta.addEventListener('input', update);
                update();
            }}
            bind();
        }})();
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
