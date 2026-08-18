import time
import uuid

import streamlit as st
from langgraph.types import Command

from ..picture.graph import create_picture_graph
from ..picture.nodes import get_entry, picture_path
from .i18n import PICTURE_CRITERION_KEYS
from .widgets import render_assessment

# In the exam the description is spoken and takes about 3 minutes.
EXAM_SECONDS = 180


@st.cache_resource
def get_picture_graph():
    return create_picture_graph()


def _reset():
    st.session_state.pic_thread = str(uuid.uuid4())
    st.session_state.pic_phase = "start"
    for key in ("pic_entry", "pic_result", "pic_deadline"):
        st.session_state.pop(key, None)


def _render_picture(T, entry):
    st.image(str(picture_path(entry)))
    st.caption(
        f"**{entry['scene']}** — "
        + T["pic_attribution"].format(
            artist=entry.get("artist") or "unknown", license=entry.get("license") or "?"
        )
    )


def render(T):
    if "pic_phase" not in st.session_state:
        _reset()

    st.header(T["pic_title"])
    graph = get_picture_graph()
    config = {"configurable": {"thread_id": st.session_state.pic_thread}}

    if st.session_state.pic_phase == "start":
        st.write(T["pic_start_hint"])
        st.markdown(T["pic_structure_hint"])
        if st.button(T["pic_start_button"], type="primary", key="pic_start"):
            result = graph.invoke(
                {
                    "language": st.session_state.language,
                    "picture_id": "", "picture_file": "", "scene": "",
                    "description": "", "feedback": "", "score": "",
                    "criterion_scores": {}, "positives": [], "missing_steps": [],
                    "errors": [],
                },
                config,
            )
            st.session_state.pic_entry = get_entry(result["picture_id"])
            st.session_state.pic_deadline = time.time() + EXAM_SECONDS
            st.session_state.pic_phase = "describing"
            st.rerun()

    elif st.session_state.pic_phase == "describing":
        entry = st.session_state.pic_entry
        _render_picture(T, entry)

        @st.fragment(run_every=1.0)
        def _timer():
            remaining = int(st.session_state.get("pic_deadline", 0) - time.time())
            if remaining > 0:
                mm, ss = divmod(remaining, 60)
                st.markdown(f"⏱ {T['pic_timer']}: **{mm}:{ss:02d}**")
            else:
                st.warning(T["pic_time_up"])

        _timer()
        with st.expander(T["task"]):
            st.markdown(T["pic_structure_hint"])

        description = st.text_area(T["pic_desc_label"], height=260, key="pic_input")

        word_count = len(description.split()) if description.strip() else 0
        colour = "green" if 60 <= word_count <= 120 else "orange"
        st.markdown(f"{T['words']}: :{colour}[**{word_count}**]")

        col1, col2 = st.columns([1, 5])
        with col1:
            submitted = st.button(
                T["submit"], type="primary", disabled=word_count < 15, key="pic_submit"
            )
        with col2:
            if st.button(T["cancel"], key="pic_cancel"):
                _reset()
                st.rerun()

        if submitted:
            with st.spinner(T["pic_evaluating"]):
                result = graph.invoke(Command(resume=description), config)
            st.session_state.pic_result = {
                "score": result.get("score", ""),
                "feedback": result.get("feedback", ""),
                "criterion_scores": result.get("criterion_scores", {}),
                "positives": result.get("positives", []),
                "missing": result.get("missing_steps", []),
                "errors": result.get("errors", []),
            }
            st.session_state.pic_phase = "done"
            st.rerun()

    elif st.session_state.pic_phase == "done":
        _render_picture(T, st.session_state.pic_entry)
        render_assessment(
            T,
            st.session_state.pic_result,
            PICTURE_CRITERION_KEYS,
            T["pic_criterion_labels"],
            T["pic_missing"],
        )
        if st.button(T["new_exercise"], type="primary", key="pic_new"):
            _reset()
            st.rerun()
