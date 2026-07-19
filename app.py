import streamlit as st

from src.ui import grammar_view, letter_view, picture_view, stats_view
from src.ui.i18n import DEFAULT_LANGUAGE, LANGUAGES, TRANSLATIONS


def main():
    if "language" not in st.session_state:
        st.session_state.language = DEFAULT_LANGUAGE

    T = TRANSLATIONS[st.session_state.language]

    st.set_page_config(page_title=T["page_title"], page_icon="🇩🇪")

    with st.sidebar:
        st.title(T["app_title"])
        lang_codes = list(LANGUAGES.keys())
        st.session_state.language = st.selectbox(
            T["language_label"],
            options=lang_codes,
            index=lang_codes.index(st.session_state.language),
            format_func=lambda code: LANGUAGES[code],
        )
    # Re-resolve in case the selector just changed the language.
    T = TRANSLATIONS[st.session_state.language]

    pages = [
        st.Page(lambda: letter_view.render(T), title=T["nav_letter"], url_path="letter"),
        st.Page(lambda: grammar_view.render(T), title=T["nav_grammar"], url_path="grammar"),
        st.Page(lambda: picture_view.render(T), title=T["nav_picture"], url_path="picture"),
        st.Page(lambda: stats_view.render(T), title=T["nav_stats"], url_path="stats"),
    ]
    st.navigation(pages).run()


if __name__ == "__main__":
    main()
