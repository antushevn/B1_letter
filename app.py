import uuid

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from langgraph.types import Command

from src import storage
from src.graph import create_graph


def _disable_spellcheck():
    """Turn off the browser's native spell-/grammar-check on the letter textarea
    so the learner writes unaided (feedback is given only after submission)."""
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

# ── Localisation ─────────────────────────────────────────────────────────────
# UI + feedback language. The task and the letter always stay German — only the
# interface labels and the LLM feedback follow this choice.
LANGUAGES = {"ru": "Русский", "de": "Deutsch", "en": "English"}
DEFAULT_LANGUAGE = "ru"

# Internal criterion keys (from criterion_scores) never change — only their labels.
CRITERION_KEYS = ("content", "communicative_structure", "linguistic_accuracy")

TRANSLATIONS = {
    "ru": {
        "page_title": "Тренировка письма B1",
        "title": "Немецкий B1 – Тренировка написания письма",
        "language_label": "Язык интерфейса и обратной связи",
        "start_hint": "Нажмите кнопку, чтобы получить новое задание.",
        "start_button": "Начать новое упражнение",
        "generating": "Генерируется задание …",
        "task": "Задание",
        "letter_label": "Напишите здесь своё письмо (100–120 слов):",
        "words": "Слов",
        "submit": "Отправить",
        "cancel": "Отмена",
        "evaluating": "Письмо оценивается …",
        "result": "Результат",
        "criteria": "Критерии",
        "missing": "Незатронутые пункты",
        "positives": "Что было хорошо",
        "errors": "Ошибки",
        "correction": "Исправление",
        "explanation": "Объяснение",
        "no_errors": "Ошибок не найдено!",
        "new_exercise": "Новое упражнение",
        "criterion_labels": {
            "content": "Содержание",
            "communicative_structure": "Коммуникативное оформление",
            "linguistic_accuracy": "Языковая правильность",
        },
        "score_labels": {"Pass": "Сдано", "Borderline": "На грани", "Fail": "Не сдано"},
        "tab_practice": "Упражнение",
        "tab_stats": "Статистика",
        "readiness_ready": "🎉 Ваш уровень достаточен для экзамена (последние {window} писем — Сдано).",
        "readiness_progress": "Серия «Сдано» подряд: {streak}/{window}.",
        "stats_no_data": "Пока нет данных. Выполните хотя бы одно упражнение.",
        "stat_streak": "Серия «Сдано»",
        "stat_total": "Всего попыток",
        "stat_pass_rate": "Доля «Сдано»",
        "stats_errors_title": "Ошибки по типам",
        "stats_errors_axis": "Количество",
        "stats_recent_title": "Последние попытки",
        "col_date": "Дата",
        "col_score": "Результат",
        "category_labels": {
            "article": "Артикль",
            "case": "Падеж",
            "word_order": "Порядок слов",
            "separable_verb": "Отделяемая приставка",
            "preposition": "Предлог",
            "verb_conjugation": "Спряжение глагола",
            "register": "Регистр (du/Sie)",
            "spelling": "Орфография",
            "greeting": "Приветствие/подпись",
            "other": "Другое",
        },
    },
    "de": {
        "page_title": "B1 Briefschreiben",
        "title": "B1 Deutsch – Briefschreiben Übung",
        "language_label": "Sprache der Oberfläche und Rückmeldung",
        "start_hint": "Klicke auf den Button, um eine neue Übungsaufgabe zu erhalten.",
        "start_button": "Neue Übung starten",
        "generating": "Aufgabe wird generiert …",
        "task": "Aufgabe",
        "letter_label": "Schreibe deinen Brief hier (100–120 Wörter):",
        "words": "Wörter",
        "submit": "Einreichen",
        "cancel": "Abbrechen",
        "evaluating": "Brief wird bewertet …",
        "result": "Ergebnis",
        "criteria": "Kriterien",
        "missing": "Nicht behandelte Punkte",
        "positives": "Was gut war",
        "errors": "Fehler",
        "correction": "Korrektur",
        "explanation": "Erklärung",
        "no_errors": "Keine Fehler gefunden!",
        "new_exercise": "Neue Übung",
        "criterion_labels": {
            "content": "Inhalt",
            "communicative_structure": "Kommunikative Gestaltung",
            "linguistic_accuracy": "Sprachliche Richtigkeit",
        },
        "score_labels": {"Pass": "Bestanden", "Borderline": "Grenzwertig", "Fail": "Nicht bestanden"},
        "tab_practice": "Übung",
        "tab_stats": "Statistik",
        "readiness_ready": "🎉 Dein Niveau reicht für die Prüfung (die letzten {window} Briefe: Bestanden).",
        "readiness_progress": "Bestanden-Serie in Folge: {streak}/{window}.",
        "stats_no_data": "Noch keine Daten. Mach zuerst eine Übung.",
        "stat_streak": "Bestanden-Serie",
        "stat_total": "Versuche gesamt",
        "stat_pass_rate": "Bestanden-Quote",
        "stats_errors_title": "Fehler nach Typ",
        "stats_errors_axis": "Anzahl",
        "stats_recent_title": "Letzte Versuche",
        "col_date": "Datum",
        "col_score": "Ergebnis",
        "category_labels": {
            "article": "Artikel",
            "case": "Kasus",
            "word_order": "Wortstellung",
            "separable_verb": "Trennbares Verb",
            "preposition": "Präposition",
            "verb_conjugation": "Konjugation",
            "register": "Register (du/Sie)",
            "spelling": "Rechtschreibung",
            "greeting": "Anrede/Grußformel",
            "other": "Sonstiges",
        },
    },
    "en": {
        "page_title": "B1 Letter Writing",
        "title": "B1 German – Letter Writing Practice",
        "language_label": "Interface and feedback language",
        "start_hint": "Click the button to get a new practice task.",
        "start_button": "Start new exercise",
        "generating": "Generating task …",
        "task": "Task",
        "letter_label": "Write your letter here (100–120 words):",
        "words": "Words",
        "submit": "Submit",
        "cancel": "Cancel",
        "evaluating": "Evaluating letter …",
        "result": "Result",
        "criteria": "Criteria",
        "missing": "Points not addressed",
        "positives": "What went well",
        "errors": "Errors",
        "correction": "Correction",
        "explanation": "Explanation",
        "no_errors": "No errors found!",
        "new_exercise": "New exercise",
        "criterion_labels": {
            "content": "Content",
            "communicative_structure": "Communicative structure",
            "linguistic_accuracy": "Linguistic accuracy",
        },
        "score_labels": {"Pass": "Pass", "Borderline": "Borderline", "Fail": "Fail"},
        "tab_practice": "Practice",
        "tab_stats": "Statistics",
        "readiness_ready": "🎉 Your level looks exam-ready (last {window} letters: Pass).",
        "readiness_progress": "Pass streak: {streak}/{window}.",
        "stats_no_data": "No data yet. Do at least one exercise.",
        "stat_streak": "Pass streak",
        "stat_total": "Total attempts",
        "stat_pass_rate": "Pass rate",
        "stats_errors_title": "Errors by type",
        "stats_errors_axis": "Count",
        "stats_recent_title": "Recent attempts",
        "col_date": "Date",
        "col_score": "Result",
        "category_labels": {
            "article": "Article",
            "case": "Case",
            "word_order": "Word order",
            "separable_verb": "Separable verb",
            "preposition": "Preposition",
            "verb_conjugation": "Conjugation",
            "register": "Register (du/Sie)",
            "spelling": "Spelling",
            "greeting": "Greeting/sign-off",
            "other": "Other",
        },
    },
}

SCORE_COLOUR = {"Pass": "green", "Borderline": "orange", "Fail": "red"}
GRADE_COLOUR = {"A": "green", "B": "blue", "C": "orange", "D": "red"}


@st.cache_resource
def get_graph():
    return create_graph()


def reset():
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.phase = "start"
    # Keep the chosen language across resets.
    for key in ("topic", "feedback", "score", "criterion_scores", "positives", "missing_points", "errors"):
        st.session_state.pop(key, None)


def render_readiness(T, attempts):
    """Exam-readiness badge (green) or the current Pass-streak progress line.
    Returns the summary dict so callers can reuse the aggregated numbers."""
    s = storage.summary(attempts)
    if s["ready"]:
        st.success(T["readiness_ready"].format(window=s["window"]))
    else:
        st.info(T["readiness_progress"].format(streak=s["streak"], window=s["window"]))
    return s


def render_stats(T):
    attempts = storage.load_attempts()
    if not attempts:
        st.info(T["stats_no_data"])
        return

    s = render_readiness(T, attempts)

    c1, c2, c3 = st.columns(3)
    c1.metric(T["stat_streak"], s["streak"])
    c2.metric(T["stat_total"], s["total"])
    c3.metric(T["stat_pass_rate"], f"{round(s['pass_rate'] * 100)}%")

    counts = storage.error_category_counts(attempts)
    if counts:
        st.subheader(T["stats_errors_title"])
        labels = T["category_labels"]
        chart = pd.DataFrame(
            {T["stats_errors_axis"]: list(counts.values())},
            index=[labels.get(k, k) for k in counts],
        )
        st.bar_chart(chart)

    st.subheader(T["stats_recent_title"])
    rows = [
        {
            T["col_date"]: (a.get("timestamp", "") or "")[:16].replace("T", " "),
            T["col_score"]: T["score_labels"].get(a.get("score", ""), a.get("score", "")),
        }
        for a in reversed(attempts[-10:])
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_practice(T, graph, config):
    # ── Start ──────────────────────────────────────────────────────────────────
    if st.session_state.phase == "start":
        lang_codes = list(LANGUAGES.keys())
        st.session_state.language = st.selectbox(
            T["language_label"],
            options=lang_codes,
            index=lang_codes.index(st.session_state.language),
            format_func=lambda code: LANGUAGES[code],
        )
        # Re-resolve translations in case the selector just changed the language.
        T = TRANSLATIONS[st.session_state.language]

        st.write(T["start_hint"])
        if st.button(T["start_button"], type="primary"):
            with st.spinner(T["generating"]):
                result = graph.invoke(
                    {
                        "language": st.session_state.language,
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
        st.subheader(T["task"])
        st.info(st.session_state.topic)

        user_letter = st.text_area(
            T["letter_label"],
            height=320,
            key="letter_input",
        )
        _disable_spellcheck()

        word_count = len(user_letter.split()) if user_letter.strip() else 0
        colour = "green" if 100 <= word_count <= 120 else "orange"
        st.markdown(f"{T['words']}: :{colour}[**{word_count}**]")

        col1, col2 = st.columns([1, 5])
        with col1:
            submitted = st.button(T["submit"], type="primary", disabled=word_count < 20)
        with col2:
            if st.button(T["cancel"]):
                reset()
                st.rerun()

        if submitted:
            with st.spinner(T["evaluating"]):
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
        st.subheader(T["task"])
        st.info(st.session_state.topic)

        # Overall score badge
        score = st.session_state.score
        colour = SCORE_COLOUR.get(score, "gray")
        score_label = T["score_labels"].get(score, score)
        st.markdown(f"### {T['result']}: :{colour}[**{score_label}**]")
        st.write(st.session_state.feedback)

        # Progress summary (Pass streak / exam readiness) across all attempts
        render_readiness(T, storage.load_attempts())

        # Criterion scores table
        cs = st.session_state.criterion_scores
        if cs:
            st.subheader(T["criteria"])
            cols = st.columns(3)
            for col, key in zip(cols, CRITERION_KEYS):
                grade = cs.get(key, "–")
                gc = GRADE_COLOUR.get(grade, "gray")
                col.metric(T["criterion_labels"][key], f":{gc}[**{grade}**]")

        # Missing points
        missing = st.session_state.missing_points
        if missing:
            st.subheader(T["missing"])
            for point in missing:
                st.markdown(f"- {point}")

        # What went well
        if st.session_state.positives:
            st.subheader(T["positives"])
            for point in st.session_state.positives:
                st.markdown(f"- {point}")

        # Errors
        errors = st.session_state.errors
        if errors:
            st.subheader(f"{T['errors']} ({len(errors)})")
            for i, err in enumerate(errors, 1):
                with st.expander(f"{i}. „{err.get('original', '')}\""):
                    st.markdown(f"**{T['correction']}:** {err.get('correction', '')}")
                    st.markdown(f"**{T['explanation']}:** {err.get('explanation', '')}")
        else:
            st.success(T["no_errors"])

        if st.button(T["new_exercise"], type="primary"):
            reset()
            st.rerun()


def main():
    if "language" not in st.session_state:
        st.session_state.language = DEFAULT_LANGUAGE
    if "phase" not in st.session_state:
        reset()

    T = TRANSLATIONS[st.session_state.language]

    st.set_page_config(page_title=T["page_title"], page_icon="✉️")
    st.title(T["title"])

    graph = get_graph()
    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    tab_practice, tab_stats = st.tabs([T["tab_practice"], T["tab_stats"]])
    with tab_practice:
        render_practice(T, graph, config)
    with tab_stats:
        render_stats(T)


if __name__ == "__main__":
    main()
