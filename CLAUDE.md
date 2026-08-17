# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A LangGraph-based trainer for the B1 German exam with three practice modules:

- **Letter** — write the exam letter (Goethe-Zertifikat B1 / telc B1 format), get examiner-style grading.
- **Grammar** — B1 grammar topics with offline exercises; topics are recommended based on the
  learner's actual error history from the other modules.
- **Picture description** — the DTZ (telc A2·B1) Sprechen Teil 2 task practised in written form;
  a vision-capable model grades the description against the actual photo.

## Stack

- Python 3.12
- LangGraph — orchestrates the letter and picture flows (human-in-the-loop interrupts)
- Anthropic Claude API — Sonnet (`claude-sonnet-5`, effort "low") for the two grading calls;
  Haiku for offline content generation and the topic fallback (see `src/common/llm.py`)
- Streamlit — multi-page web UI (`st.navigation`)

Versioning: bump `APP_VERSION` in `src/version.py` (+ pyproject) on user-visible changes —
it is shown in the sidebar and confirms which build Streamlit Cloud is serving after its
automatic redeploy from master.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. On Streamlit Community Cloud, set
`ANTHROPIC_API_KEY` in the app secrets instead (`src/common/llm.py` bridges st.secrets → env).

## Running

```bash
streamlit run app.py
```

## Architecture

```
app.py                     entry point: sidebar language selector + st.navigation
src/common/
  llm.py                   shared Anthropic client, model tiering, secrets bridge
  storage.py               attempt persistence + aggregations (all modules); MongoDB
                           backend when MONGO_URI is set, else data/history.jsonl
src/letter/                LangGraph flow: generate_topic → await_letter → check_letter
src/picture/               LangGraph flow: pick_picture → await_description → check_description
src/grammar/               no LLM: curriculum loader + deterministic checking + recommendations
src/ui/
  i18n.py                  every UI string (ru/de/en); feedback language follows the UI language
  *_view.py                one render(T) per page; widgets.py has shared render helpers
data/
  topics.json              pre-generated letter tasks (scripts/build_topic_pool.py, committed)
  grammar_curriculum.json  hand-authored: 12 topics × lesson (3 langs, markdown with tables,
                           memory hooks, typical mistakes) × 8 verified core exercises
  grammar_pool.json        extended exercise pool (scripts/build_grammar_pool.py, Batch API,
                           hand-reviewed); each drill session samples 8 random from core + pool
  pictures/ + pictures.json  photos from official DTZ model sets (g.a.s.t./BAMF/Goethe) plus a
                           few Commons photos; scripts/build_picture_pool.py only for Commons ones
  history.jsonl            append-only attempt log — file backend only (gitignored, one
                           JSON record per line); unused when MongoDB is active
```

Key design decisions:

- **Cost control**: content that can be pre-generated lives in `data/` and ships with the repo.
  The grammar module makes **zero** API calls; the letter/picture modules make exactly one grading
  call per attempt (Haiku). `await_*` nodes are `interrupt()` nodes — the graph pauses and resumes
  via `Command(resume=...)` across Streamlit reruns (MemorySaver checkpointer, thread_id per session).
- **Error taxonomy is the integration point**: `storage.ERROR_CATEGORIES` tags every graded error
  (letter + picture) and every grammar topic declares which categories it trains
  (`grammar_curriculum.json` → `categories`). `src/grammar/logic.recommend_topics()` ranks topics
  by those counts — this is how "adjust grammar to my weaknesses" works. Don't rename categories.
- **History records** always carry `module` ("letter" | "picture" | "grammar"); records without the
  field are legacy letter attempts. Grammar attempts store `wrong_categories` instead of `errors`.
- **Storage backend**: `storage.save_attempt`/`load_attempts` transparently target MongoDB when
  `MONGO_URI` is set (local `.env` or Streamlit secrets), else the local `history.jsonl` file. The
  deployed app uses Mongo so history survives the ephemeral hosted filesystem; local dev and the
  offline scripts work file-only with no extra setup. `pymongo` is imported lazily and any
  connection failure falls back to the file, so the app always runs. The stats page still offers
  JSON-lines export/import (backups, and seeding a fresh Mongo collection from an old export).

## LangGraph conventions

- State is a plain `TypedDict`; nodes are pure functions `(state) -> dict`
- `graph.compile(checkpointer=MemorySaver())` so interrupts persist between Streamlit rerenders
- Invoke with `graph.invoke(state, config={"configurable": {"thread_id": session_id}})`

## Testing note

Grading calls cost money — when testing, prefer the grammar module (fully offline) and avoid
submitting letters/descriptions unless the grading path itself changed.
