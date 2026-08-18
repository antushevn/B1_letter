"""Reference page: model letters (Musterbriefe) + a phrase bank (Redemittel)
for the telc B1 letter task. Pure reference content — no LLM, no attempts saved.

The German phrases and letters are never translated (they are what the learner
memorises); only the structural labels — category names, functional groups,
section headers — follow the interface language via i18n.
"""

import streamlit as st

from ..reference.content import load_letters, load_redemittel


def _hard_breaks(text: str) -> str:
    """Keep every source line on its own line in st.markdown (which otherwise
    merges single newlines) — matters for the greeting/signature and Leitpunkte."""
    return text.replace("\n", "  \n")


def _render_letters(T):
    letters = load_letters()
    reg_labels = T["ref_register_labels"]
    cat_labels = T["ref_category_labels"]

    for register in ("formell", "informell"):
        group = [l for l in letters if l["register"] == register]
        if not group:
            continue
        st.subheader(reg_labels.get(register, register))
        for letter in group:
            category = cat_labels.get(letter["category"], letter["category"])
            with st.expander(f"{category} · {letter['title']}"):
                st.markdown(f"**{T['ref_situation']}**")
                with st.container(border=True):
                    st.markdown(_hard_breaks(letter["situation"]))

                st.markdown(f"**{T['ref_model']}**")
                with st.container(border=True):
                    st.markdown(_hard_breaks(letter["letter"]))

                st.markdown(f"**{T['ref_highlights']}**")
                for phrase in letter["highlights"]:
                    st.markdown(f"- {phrase}")


def _render_phrases(T):
    st.caption(T["ref_phrases_intro"])
    func_labels = T["ref_function_labels"]
    for group in load_redemittel():
        label = func_labels.get(group["function"], group["function"])
        st.markdown(f"**{label}**")
        with st.container(border=True):
            for phrase in group["phrases"]:
                st.markdown(f"- {phrase}")


def render(T):
    st.header(T["ref_title"])
    st.caption(T["ref_intro"])

    tab_letters, tab_phrases = st.tabs([T["ref_tab_letters"], T["ref_tab_phrases"]])
    with tab_letters:
        _render_letters(T)
    with tab_phrases:
        _render_phrases(T)
