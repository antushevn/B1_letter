import uuid

import streamlit as st
from langgraph.types import Command

from src.graph import create_graph

CRITERION_LABELS = {
    "content": "Inhalt",
    "communicative_structure": "Kommunikative Gestaltung",
    "linguistic_accuracy": "Sprachliche Richtigkeit",
}

SCORE_COLOUR = {"Pass": "green", "Borderline": "orange", "Fail": "red"}
GRADE_COLOUR = {"A": "green", "B": "blue", "C": "orange", "D": "red"}


@st.cache_resource
def get_graph():
    return create_graph()


def reset():
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.phase = "start"
    for key in ("topic", "feedback", "score", "criterion_scores", "positives", "missing_points", "errors"):
        st.session_state.pop(key, None)


def main():
    st.set_page_config(page_title="B1 Briefschreiben", page_icon="✉️")
    st.title("B1 Deutsch – Briefschreiben Übung")

    if "phase" not in st.session_state:
        reset()

    graph = get_graph()
    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    # ── Start ──────────────────────────────────────────────────────────────────
    if st.session_state.phase == "start":
        st.write("Klicke auf den Button, um eine neue Übungsaufgabe zu erhalten.")
        if st.button("Neue Übung starten", type="primary"):
            with st.spinner("Aufgabe wird generiert …"):
                result = graph.invoke(
                    {
                        "topic": "", "user_letter": "", "feedback": "", "score": "",
                        "criterion_scores": {}, "positives": [], "missing_points": [], "errors": [],
                    },
                    config,
                )
            st.session_state.topic = result["topic"]
            st.session_state.phase = "writing"
            st.rerun()

    # ── Writing ────────────────────────────────────────────────────────────────
    elif st.session_state.phase == "writing":
        st.subheader("Aufgabe")
        st.info(st.session_state.topic)

        user_letter = st.text_area(
            "Schreibe deinen Brief hier (100–120 Wörter):",
            height=320,
            key="letter_input",
        )

        word_count = len(user_letter.split()) if user_letter.strip() else 0
        colour = "green" if 100 <= word_count <= 120 else "orange"
        st.markdown(f"Wörter: :{colour}[**{word_count}**]")

        col1, col2 = st.columns([1, 5])
        with col1:
            submitted = st.button("Einreichen", type="primary", disabled=word_count < 20)
        with col2:
            if st.button("Abbrechen"):
                reset()
                st.rerun()

        if submitted:
            with st.spinner("Brief wird bewertet …"):
                result = graph.invoke(Command(resume=user_letter), config)
            st.session_state.feedback = result.get("feedback", "")
            st.session_state.score = result.get("score", "")
            st.session_state.criterion_scores = result.get("criterion_scores", {})
            st.session_state.positives = result.get("positives", [])
            st.session_state.missing_points = result.get("missing_points", [])
            st.session_state.errors = result.get("errors", [])
            st.session_state.phase = "done"
            st.rerun()

    # ── Done ───────────────────────────────────────────────────────────────────
    elif st.session_state.phase == "done":
        st.subheader("Aufgabe")
        st.info(st.session_state.topic)

        # Overall score badge
        score = st.session_state.score
        colour = SCORE_COLOUR.get(score, "gray")
        st.markdown(f"### Ergebnis: :{colour}[**{score}**]")
        st.write(st.session_state.feedback)

        # Criterion scores table
        cs = st.session_state.criterion_scores
        if cs:
            st.subheader("Kriterien")
            cols = st.columns(3)
            for col, (key, label) in zip(cols, CRITERION_LABELS.items()):
                grade = cs.get(key, "–")
                gc = GRADE_COLOUR.get(grade, "gray")
                col.metric(label, f":{gc}[**{grade}**]")

        # Missing points
        missing = st.session_state.missing_points
        if missing:
            st.subheader("Nicht behandelte Punkte")
            for point in missing:
                st.markdown(f"- {point}")

        # What went well
        if st.session_state.positives:
            st.subheader("Was gut war")
            for point in st.session_state.positives:
                st.markdown(f"- {point}")

        # Errors
        errors = st.session_state.errors
        if errors:
            st.subheader(f"Fehler ({len(errors)})")
            for i, err in enumerate(errors, 1):
                with st.expander(f"{i}. „{err.get('original', '')}\""):
                    st.markdown(f"**Korrektur:** {err.get('correction', '')}")
                    st.markdown(f"**Erklärung:** {err.get('explanation', '')}")
        else:
            st.success("Keine Fehler gefunden!")

        if st.button("Neue Übung", type="primary"):
            reset()
            st.rerun()


if __name__ == "__main__":
    main()
