import pandas as pd
import streamlit as st

from ..common import storage
from ..grammar.content import load_topics
from .widgets import render_readiness


def _weak_areas_chart(T, attempts):
    counts = storage.error_category_counts(attempts)
    if not counts:
        return
    st.subheader(T["stats_weak_title"])
    st.caption(T["stats_weak_caption"])
    labels = T["category_labels"]
    chart = pd.DataFrame(
        {T["stats_errors_axis"]: list(counts.values())},
        index=[labels.get(k, k) for k in counts],
    )
    st.bar_chart(chart)


def _scored_module_tab(T, attempts, extra_col=None):
    """Shared layout for the Pass/Fail-scored modules (letter, picture)."""
    if not attempts:
        st.info(T["stats_no_data"])
        return
    s = render_readiness(T, attempts)
    c1, c2, c3 = st.columns(3)
    c1.metric(T["stat_streak"], s["streak"])
    c2.metric(T["stat_total"], s["total"])
    c3.metric(T["stat_pass_rate"], f"{round(s['pass_rate'] * 100)}%")

    st.subheader(T["stats_recent_title"])
    rows = []
    for a in reversed(attempts[-10:]):
        row = {
            T["col_date"]: (a.get("timestamp", "") or "")[:16].replace("T", " "),
            T["col_score"]: T["score_labels"].get(a.get("score", ""), a.get("score", "")),
        }
        if extra_col:
            key, label = extra_col
            row[label] = a.get(key, "")
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _grammar_tab(T):
    attempts = storage.load_attempts("grammar")
    if not attempts:
        st.info(T["stats_no_data"])
        return
    stats = storage.grammar_topic_stats(attempts)
    titles = {t["id"]: t["title"] for t in load_topics()}
    rows = [
        {
            T["col_topic"]: titles.get(topic_id, topic_id),
            T["col_attempts"]: s["attempts"],
            T["col_accuracy"]: f"{round(s['accuracy'] * 100)}%",
        }
        for topic_id, s in sorted(
            stats.items(), key=lambda kv: kv[1]["accuracy"]
        )
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _backup_section(T):
    with st.expander(T["backup_title"]):
        backend = storage.backend_name()
        st.caption(T["backup_backend"].format(backend=T[f"backup_backend_{backend}"]))
        st.caption(T["backup_caption_mongodb"] if backend == "mongodb" else T["backup_caption"])
        data = storage.export_bytes()
        if data:
            st.download_button(
                T["backup_download"],
                data=data,
                file_name="b1_history.jsonl",
                mime="application/jsonl",
                key="backup_download",
            )
        uploaded = st.file_uploader(T["backup_upload"], type=["jsonl", "txt"], key="backup_upload")
        if uploaded is not None and st.session_state.get("backup_imported") != uploaded.file_id:
            try:
                n = storage.import_bytes(uploaded.getvalue())
            except ValueError:
                st.error(T["backup_error"])
            else:
                st.session_state.backup_imported = uploaded.file_id
                st.success(T["backup_success"].format(n=n))


def render(T):
    st.header(T["stats_title"])

    all_attempts = storage.load_attempts()
    if not all_attempts:
        st.info(T["stats_no_data"])
        _backup_section(T)
        return

    _weak_areas_chart(T, all_attempts)

    tab_letter, tab_picture, tab_grammar = st.tabs(
        [T["tab_letter"], T["tab_picture"], T["tab_grammar"]]
    )
    with tab_letter:
        _scored_module_tab(T, storage.load_attempts("letter"))
    with tab_picture:
        _scored_module_tab(
            T, storage.load_attempts("picture"), extra_col=("scene", T["col_scene"])
        )
    with tab_grammar:
        _grammar_tab(T)

    _backup_section(T)
