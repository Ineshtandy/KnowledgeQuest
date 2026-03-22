# Adaptive Tutor

Local-first adaptive learning backend using LangGraph orchestration, Gemini agents, and SQLite persistence.

## Quick start

1. Create or activate your Python environment.
2. Install dependencies:
   - `pip install -e .[dev]`
3. Copy environment values:
   - `cp .env.example .env`
4. Run local demo:
   - `python run_demo.py`
5. Run API:
   - `uvicorn adaptive_tutor.api.main:app --reload`

## Notes

- The engine owns progression and routing decisions.
- Agents produce validated structured outputs only.
- LangGraph orchestrates node transitions and pause/resume.
