import uuid

import streamlit as st
from langgraph.types import Command

from ..common import storage
from ..letter.graph import create_graph
from .i18n import LETTER_CRITERION_KEYS
from .widgets import (
    render_assessment,
    render_readiness,
    word_count_line,
)

WC_LOW, WC_HIGH = 130, 170


@st.cache_resource
def get_letter_graph():
    return create_graph()


def _reset():
    st.session_state.letter_thread = str(uuid.uuid4())
    st.session_state.letter_phase = "start"
    st.session_state.pop("letter_topic", None)
    st.session_state.pop("letter_result", None)


def render(T):
    if "letter_phase" not in st.session_state:
        _reset()

    st.header(T["letter_title"])
    graph = get_letter_graph()
    config = {"configurable": {"thread_id": st.session_state.letter_thread}}

    if st.session_state.letter_phase == "start":
        st.write(T["start_hint"])
        if st.button(T["start_button"], type="primary", key="letter_start"):
            with st.spinner(T["generating"]):
                result = graph.invoke(
                    {
                        "language": st.session_state.language,
                        "topic": "", "user_letter": "", "feedback": "", "score": "",
                        "criterion_scores": {}, "positives": [], "missing_points": [],
                        "errors": [],
                    },
                    config,
                )
            st.session_state.letter_topic = result["topic"]
            st.session_state.letter_phase = "writing"
            st.rerun()

    elif st.session_state.letter_phase == "writing":
        st.subheader(T["task"])
        st.info(st.session_state.letter_topic)

        user_letter = st.text_area(T["letter_label"], height=320, key="letter_input")

        word_count = len(user_letter.split()) if user_letter.strip() else 0
        word_count_line(T, word_count, WC_LOW, WC_HIGH)

        col1, col2 = st.columns([1, 5])
        with col1:
            submitted = st.button(
                T["submit"], type="primary", disabled=word_count < 20, key="letter_submit"
            )
        with col2:
            if st.button(T["cancel"], key="letter_cancel"):
                _reset()
                st.rerun()

        if submitted:
            with st.spinner(T["evaluating"]):
                result = graph.invoke(Command(resume=user_letter), config)
            st.session_state.letter_result = {
                "user_letter": user_letter,
                "score": result.get("score", ""),
                "feedback": result.get("feedback", ""),
                "criterion_scores": result.get("criterion_scores", {}),
                "positives": result.get("positives", []),
                "missing": result.get("missing_points", []),
                "errors": result.get("errors", []),
            }
            st.session_state.letter_phase = "done"
            st.rerun()

    elif st.session_state.letter_phase == "done":
        st.subheader(T["task"])
        st.info(st.session_state.letter_topic)

        letter_text = st.session_state.letter_result.get("user_letter", "")
        if letter_text:
            with st.expander(T["your_letter"], expanded=True):
                st.text(letter_text)

        render_assessment(
            T,
            st.session_state.letter_result,
            LETTER_CRITERION_KEYS,
            T["letter_criterion_labels"],
            T["missing"],
        )
        render_readiness(T, storage.load_attempts("letter"))

        if st.button(T["new_exercise"], type="primary", key="letter_new"):
            _reset()
            st.rerun()
