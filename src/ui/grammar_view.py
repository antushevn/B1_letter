import streamlit as st

from ..common import storage
from ..grammar.content import get_topic
from ..grammar.logic import grade_session, recommend_topics, sample_session


def _new_session(topic_id: str):
    """Draw a fresh random exercise set; the nonce gives widgets new keys so
    previous answers don't leak into the new set."""
    st.session_state.gram_exercises = sample_session(get_topic(topic_id))
    st.session_state.gram_nonce = st.session_state.get("gram_nonce", 0) + 1
    st.session_state.pop("gram_results", None)


def _open_topic(topic_id: str):
    st.session_state.gram_topic_id = topic_id
    _new_session(topic_id)


def _back_to_list():
    st.session_state.pop("gram_topic_id", None)
    st.session_state.pop("gram_results", None)
    st.session_state.pop("gram_exercises", None)


def _render_topic_list(T, lang: str):
    st.caption(T["gram_intro"])
    ranked = recommend_topics(storage.load_attempts())

    if all(r["weakness"] == 0 for r in ranked):
        st.info(T["gram_no_history"])

    for r in ranked:
        topic = r["topic"]
        mastery = r["mastery"]
        with st.container(border=True):
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                badges = []
                if r["recommended"]:
                    badges.append(T["gram_recommended"])
                if mastery["mastered"]:
                    badges.append(T["gram_mastered"])
                title_line = f"**{topic['title']}**"
                if badges:
                    title_line += "  " + " · ".join(badges)
                st.markdown(title_line)

                details = [T["gram_errors_hit"].format(n=r["weakness"])]
                if mastery["answered"]:
                    details.append(
                        T["gram_accuracy"].format(pct=round(mastery["accuracy"] * 100))
                    )
                st.caption(" · ".join(details))
            with col_btn:
                st.button(
                    T["gram_practice_button"],
                    key=f"gram_open_{topic['id']}",
                    on_click=_open_topic,
                    args=(topic["id"],),
                )


def _render_topic(T, lang: str, topic: dict):
    st.button(T["gram_back"], key="gram_back", on_click=_back_to_list)
    st.subheader(topic["title"])

    st.markdown(f"**{T['gram_rule']}**")
    # Bordered container instead of st.info: lessons contain markdown tables,
    # which alert boxes don't render.
    with st.container(border=True):
        st.markdown(topic["rule"].get(lang) or topic["rule"]["en"])

    st.markdown(f"**{T['gram_examples']}**")
    for example in topic["examples"]:
        st.markdown(f"- {example}")

    st.markdown(f"**{T['gram_exercises']}**")
    if "gram_exercises" not in st.session_state:
        _new_session(topic["id"])
    exercises = st.session_state.gram_exercises
    nonce = st.session_state.get("gram_nonce", 0)
    results = st.session_state.get("gram_results")

    with st.form(key=f"gram_form_{nonce}"):
        answers = []
        for i, ex in enumerate(exercises):
            st.markdown(f"**{i + 1}.** {ex['prompt']}")
            if ex["type"] == "mc":
                answer = st.radio(
                    T["gram_answer_label"],
                    options=range(len(ex["options"])),
                    format_func=lambda idx, opts=ex["options"]: opts[idx],
                    index=None,
                    key=f"gram_{nonce}_{i}",
                    label_visibility="collapsed",
                )
            else:
                answer = st.text_input(
                    T["gram_answer_label"],
                    key=f"gram_{nonce}_{i}",
                )
            answers.append(answer)
        submitted = st.form_submit_button(T["gram_check"], type="primary")

    if submitted:
        if any(a is None or (isinstance(a, str) and not a.strip()) for a in answers):
            st.warning(T["gram_incomplete"])
            return
        graded = grade_session(topic, exercises, answers)
        graded["answers"] = answers
        storage.save_attempt(graded["record"], module="grammar")
        st.session_state.gram_results = graded
        results = graded

    if results:
        st.markdown(f"### {T['gram_result'].format(correct=results['correct'], total=results['total'])}")
        for i, (ex, ok, answer) in enumerate(
            zip(exercises, results["results"], results["answers"])
        ):
            given = ex["options"][answer] if ex["type"] == "mc" else answer
            if ok:
                st.success(f"**{i + 1}.** {T['gram_correct']}: {given}")
            else:
                correct = (
                    ex["options"][ex["answer"]] if ex["type"] == "mc" else ex["accepted"][0]
                )
                explanation = ex["explanation"].get(lang) or ex["explanation"]["en"]
                st.error(
                    f"**{i + 1}.** {T['gram_wrong']}: {given}\n\n"
                    f"**{T['gram_correct_answer']}:** {correct}\n\n{explanation}"
                )
        st.button(
            T["gram_try_again"],
            type="primary",
            key=f"gram_again_{nonce}",
            on_click=_new_session,
            args=(topic["id"],),
        )


def render(T):
    st.header(T["gram_title"])
    lang = st.session_state.language

    topic_id = st.session_state.get("gram_topic_id")
    topic = get_topic(topic_id) if topic_id else None
    if topic:
        _render_topic(T, lang, topic)
    else:
        _render_topic_list(T, lang)
