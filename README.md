# KnowledgeQuest — Adaptive Tutor

Local-first adaptive tutoring prototype built around a LangGraph workflow, Gemini-powered agents, a FastAPI backend, and SQLite persistence. This repo also includes a lightweight Pygame “boss fight” frontend that talks to the API.

## Repository layout

- `adaptive_tutor/` — Python package + demo frontend/assets
  - `src/adaptive_tutor/` — core engine, workflow graph, API
  - `tests/` — unit tests
- `data/app.db` — default SQLite database location (created on demand)

## Setup

Prereqs: Python 3.11+.

From the repo root:

1. Install dependencies (editable + dev tools):
   - `python -m pip install -e adaptive_tutor[dev]`
2. Create environment file:
   - `cp adaptive_tutor/.env.example adaptive_tutor/.env`
3. Set at least:
   - `GEMINI_API_KEY=...`

Optional config (see `adaptive_tutor/src/adaptive_tutor/config.py`):

- `GEMINI_MODEL` (default: `gemini-2.5-flash`)
- `APP_DB_PATH` (default: `data/app.db` at repo root)

## Run

### API (FastAPI)

Run from `adaptive_tutor/` so the local `.env` is picked up reliably:

- `cd adaptive_tutor && uvicorn adaptive_tutor.api.main:app --host 127.0.0.1 --port 8000 --reload`

API routes:

- `POST /sessions` (body: `{ "topic": "..." }`) → returns the first question
- `GET /sessions/{session_id}` → returns current session state
- `POST /sessions/{session_id}/answer` (body: `{ "answer": "..." }`) → evaluation/teaching + next question

### CLI demo

- `cd adaptive_tutor && python run_demo.py`

### Pygame frontend (boss fight)

In one terminal, start the API. In another:

- `cd adaptive_tutor && python frontend.py`

Notes:

- The frontend expects `pygame` and `Pillow` to be available in your environment.
- It uses local assets in `adaptive_tutor/` and calls the API at `http://127.0.0.1:8000`.

## Persistence

SQLite persistence is managed via SQLAlchemy and defaults to `data/app.db` (repo root). Sessions, attempts, and teaching events are stored and can be reconstructed.

There’s a helper script to validate DB-backed resume behavior without needing the frontend:

- `python adaptive_tutor/verify_persistence.py --mode seed`
- `python adaptive_tutor/verify_persistence.py --mode inspect --db data/app.db --list-sessions 10`

## Tests

After installing deps:

- `cd adaptive_tutor && pytest`

If you see import errors like missing `fastapi`, `langgraph`, or `google.genai`, it usually means the current Python environment didn’t have dependencies installed (re-run the editable install command above in the same environment).
