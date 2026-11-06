# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"Spendly" — a Flask expense tracker built as a step-by-step teaching project. Only the landing, auth pages, and legal pages exist so far; most backend functionality is intentionally stubbed for later steps.

## Commands

```
pip install -r requirements.txt     # flask, werkzeug, pytest, pytest-flask
python app.py                       # dev server at http://localhost:5001 (debug=True)
pytest                              # run tests (no tests exist yet)
pytest path/to/test_file.py::test_name   # run a single test
```

A `venv/` directory is checked out locally (git-ignored). 

## Architecture

- `app.py` — single Flask app with all routes. `/`, `/register`, `/login`, `/terms`, `/privacy` render templates (register/login are GET-only, no form handling yet). `/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete` are placeholder routes returning plain strings labelled with the tutorial step that should implement them ("Step 3", "Step 4", "Step 7–9") — replace these rather than adding duplicates.
- `database/db.py` — currently only a comment stub describing the intended contract: `get_db()` (SQLite connection with `row_factory` and foreign keys enabled), `init_db()` (`CREATE TABLE IF NOT EXISTS`), `seed_db()` (sample data). Follow that contract when implementing (Step 1).
- `templates/` — Jinja templates all extending `base.html` (navbar, `title`/`head`/`content` blocks, Google Fonts DM Serif Display + DM Sans). Link with `url_for(...)`.
- `static/css/style.css` is loaded globally by `base.html`; `landing.css` is page-specific (landing page). `static/js/main.js` is currently empty.
