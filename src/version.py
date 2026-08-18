"""Single source of truth for the app version, shown in the sidebar.

Bump on every user-visible change before pushing — Streamlit Cloud redeploys
automatically from master, and the sidebar number is how we confirm the new
build is live. Keep pyproject.toml's [project] version in sync.
"""

APP_VERSION = "0.4.2"
