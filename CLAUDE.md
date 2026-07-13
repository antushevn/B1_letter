# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A LangGraph-based tool for practicing the letter-writing section of the B1 German language exam. The flow generates a topic, receives the user's letter, then analyses it and highlights errors.

## Stack

- Python 3.12
- LangGraph — orchestrates the multi-step practice flow
- Anthropic Claude API — LLM for topic generation, error checking, and feedback
- Streamlit (likely) — local web UI

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`.

## Running

```bash
# Web UI
streamlit run app.py

# Flow only (no UI)
python -m src.main
```

## Architecture

The core is a LangGraph `StateGraph` whose state carries the full session: topic, user letter, and feedback.

```
generate_topic → await_letter → check_letter → (done)
```

Key modules:

- `src/state.py` — TypedDict defining `PracticeState` (topic, user_letter, feedback, errors)
- `src/nodes.py` — one function per graph node; each takes and returns `PracticeState`
- `src/graph.py` — assembles the `StateGraph`, defines edges and entry/end points
- `src/prompts.py` — all Claude prompt templates (topic generation, error analysis)
- `app.py` — Streamlit UI; drives the graph by invoking nodes and reading state

`await_letter` is a human-in-the-loop interrupt node — the graph pauses there and resumes when the user submits their letter.

## LangGraph conventions

- State is a plain `TypedDict`; nodes are pure functions `(state: PracticeState) -> dict`
- Use `graph.compile(checkpointer=...)` with `MemorySaver` for local runs so the human-in-the-loop interrupt persists between Streamlit rerenders
- Invoke with `graph.invoke(state, config={"configurable": {"thread_id": session_id}})`
