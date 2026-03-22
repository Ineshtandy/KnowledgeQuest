"""Validate persistence and DB-backed resume behavior.

Two modes:
- seed: creates an isolated temp SQLite DB, seeds deterministic rows (no LLM calls),
  validates repository retrieval + load_session reconstruction + runner.resume_session
  in a fresh process.
- inspect: reads an existing SQLite DB (optionally via a safety copy), prints a
  transcript for a chosen session, validates load_session + fresh-process
  runner.resume_session.

This script intentionally avoids touching the frontend.

Run examples:
- Seeded deterministic validation:
  python adaptive_tutor/verify_persistence.py --mode seed

- Inspect an existing DB (list sessions):
    python adaptive_tutor/verify_persistence.py --mode inspect --db data/app.db --list-sessions 10

- Inspect a specific session:
    python adaptive_tutor/verify_persistence.py --mode inspect --db data/app.db --session-id <uuid>
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parent
SRC_DIR = REPO_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@dataclass(frozen=True)
class ScriptConfig:
    mode: str
    db_path: Path | None
    session_id: str | None
    list_sessions: int | None
    keep_db: bool
    no_copy: bool


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate persistence + resume from DB")

    parser.add_argument(
        "--mode",
        choices=("seed", "inspect"),
        default=None,
        help="seed: deterministic temp DB; inspect: read existing DB",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to SQLite DB. If provided and --mode is omitted, defaults to inspect.",
    )
    parser.add_argument("--session-id", type=str, default=None, help="Session UUID to inspect")
    parser.add_argument(
        "--list-sessions",
        type=int,
        default=None,
        help="List N most recent sessions (inspect mode).",
    )
    parser.add_argument(
        "--keep-db",
        action="store_true",
        help="Keep temp DB/copy on disk (useful for debugging).",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Inspect mode only: use DB directly (default is copy-to-temp for safety).",
    )

    # Internal: child mode used to force runner.resume_session to load from DB.
    parser.add_argument("--resume-child", action="store_true", help=argparse.SUPPRESS)

    return parser.parse_args(argv)


def _resolve_config(ns: argparse.Namespace) -> ScriptConfig:
    mode = ns.mode
    db_path = Path(ns.db).expanduser().resolve() if ns.db else None

    if mode is None:
        mode = "inspect" if db_path is not None else "seed"

    return ScriptConfig(
        mode=mode,
        db_path=db_path,
        session_id=ns.session_id,
        list_sessions=ns.list_sessions,
        keep_db=bool(ns.keep_db),
        no_copy=bool(ns.no_copy),
    )


def _set_db_env(db_path: Path) -> None:
    os.environ["APP_DB_PATH"] = str(db_path)


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _copy_db_for_inspection(db_path: Path) -> Path:
    if not db_path.exists():
        raise FileNotFoundError(f"DB file not found: {db_path}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="adaptive_tutor_inspect_db_"))
    copied = tmp_dir / "app_copy.db"
    shutil.copy2(db_path, copied)
    return copied


def _session_count_for_db(db_path: Path) -> int | None:
    if not db_path.exists():
        return None
    try:
        with sqlite3.connect(str(db_path)) as con:
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM sessions")
            row = cur.fetchone()
            return int(row[0]) if row else 0
    except sqlite3.Error:
        return None


def _warn_if_other_db_has_more_sessions(selected_db: Path) -> None:
    selected_count = _session_count_for_db(selected_db)
    if selected_count is None:
        return

    repo_root = REPO_DIR.parent
    candidates = [
        REPO_DIR / "data" / "app.db",
        repo_root / "data" / "app.db",
    ]

    best_path = selected_db
    best_count = selected_count
    for candidate in candidates:
        if candidate.resolve() == selected_db.resolve():
            continue
        count = _session_count_for_db(candidate)
        if count is None:
            continue
        if count > best_count:
            best_count = count
            best_path = candidate

    if best_path.resolve() != selected_db.resolve():
        print(
            "Warning: another likely DB has more sessions.\n"
            f"  selected: {selected_db} (sessions={selected_count})\n"
            f"  candidate: {best_path} (sessions={best_count})"
        )


def _import_after_env() -> None:
    # Placeholder to make intent obvious when reading the script.
    return


def _list_recent_sessions(limit: int) -> list[dict]:
    from sqlalchemy import desc, select

    from adaptive_tutor.models.db_models import SessionDB
    from adaptive_tutor.storage.database import session_scope

    with session_scope() as session:
        result = session.execute(select(SessionDB).order_by(desc(SessionDB.created_at)).limit(limit))
        rows = list(result.scalars().all())

    return [
        {
            "session_id": r.id,
            "topic": r.topic,
            "status": r.status,
            "current_level_index": r.current_level_index,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


def _format_attempt(a) -> str:
    # a is AttemptDB
    correctness = "correct" if a.is_correct else "incorrect"
    return (
        f"Attempt {a.id}\n"
        f"  level={a.level_index} question_id={a.question_id} type={a.question_type}\n"
        f"  Q: {a.question_text}\n"
        f"  A: {a.user_answer}\n"
        f"  eval: {correctness} score={a.score} tag={a.misconception_tag}\n"
        f"  feedback: {a.feedback}\n"
        f"  next_action: {a.next_action}\n"
        f"  at: {a.created_at.isoformat()}\n"
    )


def _format_teaching(t) -> str:
    return (
        f"Teaching {t.id}\n"
        f"  level={t.level_index} question_id={t.question_id}\n"
        f"  summary: {t.summary}\n"
        f"  why: {t.why_user_was_wrong}\n"
        f"  example: {t.worked_example}\n"
        f"  tip: {t.memory_tip}\n"
        f"  checkpoint: {t.checkpoint_question}\n"
        f"  at: {t.created_at.isoformat()}\n"
    )


def _print_transcript(session_id: str) -> None:
    from adaptive_tutor.storage import repositories

    attempts = repositories.list_attempts_for_session(session_id)
    teachings = repositories.list_teachings_for_session(session_id)

    print(f"\n=== Transcript for session {session_id} ===")
    print(f"Attempts: {len(attempts)}")
    for a in attempts:
        print(_format_attempt(a))

    print(f"Teachings: {len(teachings)}")
    for t in teachings:
        print(_format_teaching(t))


def _validate_retrieval_ordering(session_id: str) -> None:
    from adaptive_tutor.storage import repositories

    attempts = repositories.list_attempts_for_session(session_id)
    if any(attempts[i].created_at > attempts[i + 1].created_at for i in range(len(attempts) - 1)):
        raise AssertionError("Attempts are not ordered by created_at ascending")

    teachings = repositories.list_teachings_for_session(session_id)
    if any(teachings[i].created_at > teachings[i + 1].created_at for i in range(len(teachings) - 1)):
        raise AssertionError("Teachings are not ordered by created_at ascending")


def _validate_load_session_snapshot(session_id: str) -> dict:
    from adaptive_tutor.engine.session_manager import load_session

    state = load_session(session_id)
    if state is None:
        raise AssertionError("load_session returned None (session missing)")

    dumped = state.model_dump()

    print("\n=== load_session snapshot ===")
    print(json.dumps(
        {
            "session_id": dumped.get("session_id"),
            "topic": dumped.get("topic"),
            "current_level_index": dumped.get("current_level_index"),
            "last_user_answer": dumped.get("last_user_answer"),
            "last_evaluation": (dumped.get("last_evaluation") or {}).get("feedback"),
            "has_teaching": dumped.get("current_teaching") is not None,
            "session_complete": dumped.get("session_complete"),
        },
        indent=2,
        ensure_ascii=False,
    ))

    return dumped


def _run_resume_child(script_path: Path, session_id: str, env: dict[str, str]) -> dict:
    cmd = [sys.executable, str(script_path), "--resume-child", "--session-id", session_id]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise RuntimeError(
            "Child resume process failed\n"
            f"cmd: {' '.join(cmd)}\n"
            f"stdout: {proc.stdout}\n"
            f"stderr: {proc.stderr}\n"
        )

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Child output was not valid JSON. stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}") from exc


def _validate_runner_resume_from_db(session_id: str, expected: dict) -> None:
    script_path = Path(__file__).resolve()
    env = os.environ.copy()

    child_data = _run_resume_child(script_path, session_id, env=env)

    print("\n=== runner.resume_session (fresh process) ===")
    print(json.dumps(child_data, indent=2, ensure_ascii=False))

    if child_data.get("session_id") != expected.get("session_id"):
        raise AssertionError("resume_session session_id mismatch")

    # These are the most important, stable invariants.
    if child_data.get("topic") != expected.get("topic"):
        raise AssertionError("resume_session topic mismatch")

    if int(child_data.get("current_level_index") or 0) != int(expected.get("current_level_index") or 0):
        raise AssertionError("resume_session current_level_index mismatch")

    exp_eval = expected.get("last_evaluation")
    child_eval = child_data.get("evaluation")
    if exp_eval is None:
        if child_eval is not None:
            raise AssertionError("resume_session returned evaluation but load_session had none")
    else:
        if child_eval is None:
            raise AssertionError("resume_session evaluation missing")
        if (child_eval.get("feedback") or "") != (exp_eval.get("feedback") or ""):
            raise AssertionError("resume_session evaluation.feedback mismatch")

    exp_teaching = expected.get("current_teaching")
    child_teaching = child_data.get("teaching")
    if exp_teaching is None:
        if child_teaching is not None:
            raise AssertionError("resume_session returned teaching but load_session had none")
    else:
        if child_teaching is None:
            raise AssertionError("resume_session teaching missing")
        if (child_teaching.get("summary") or "") != (exp_teaching.get("summary") or ""):
            raise AssertionError("resume_session teaching.summary mismatch")


def _seed_deterministic_data() -> str:
    from adaptive_tutor.storage import repositories

    session_row = repositories.create_session(topic="persistence-test")
    session_id = session_row.id

    # Two attempts, one with multi-paragraph feedback.
    repositories.create_attempt(
        session_id=session_id,
        level_index=0,
        question_id="q1",
        question_text="Explain what a variable is.",
        question_type="short_answer",
        expected_key_points=["name", "value", "storage"],
        user_answer="A variable is a box.",
        is_correct=False,
        score=0.2,
        misconception_tag="variable-as-box-only",
        feedback="Not quite.\n\nA variable is a *name* that refers to a value.",
        next_action="TEACH",
    )

    repositories.create_teaching(
        session_id=session_id,
        level_index=0,
        question_id="q1",
        summary="A variable is a name bound to a value.",
        why_user_was_wrong="You described a metaphor but missed the idea of binding a name to a value.",
        worked_example="x = 3 means the name x refers to the value 3.",
        memory_tip="Think: name → value.",
        checkpoint_question="What does x refer to after x = 10?",
    )

    repositories.create_attempt(
        session_id=session_id,
        level_index=0,
        question_id="q2",
        question_text="What does x refer to after x = 10?",
        question_type="short_answer",
        expected_key_points=["10"],
        user_answer="It refers to 10.",
        is_correct=True,
        score=1.0,
        misconception_tag=None,
        feedback="Correct.",
        next_action="CONTINUE",
    )

    return session_id


def _main_seed(cfg: ScriptConfig) -> int:
    tmp_dir = Path(tempfile.mkdtemp(prefix="adaptive_tutor_seed_db_"))
    db_path = tmp_dir / "seed.db"

    try:
        _ensure_parent_dir(db_path)
        _set_db_env(db_path)

        from adaptive_tutor.storage.database import init_db

        init_db()

        session_id = _seed_deterministic_data()

        _validate_retrieval_ordering(session_id)
        _print_transcript(session_id)

        loaded = _validate_load_session_snapshot(session_id)
        _validate_runner_resume_from_db(session_id, expected=loaded)

        print("\n✅ Seed mode validation passed")
        return 0
    finally:
        if cfg.keep_db:
            print(f"\nKeeping seeded DB at: {db_path}")
        else:
            # Keep evidence on failure: if an exception is raised, the process will exit non-zero and
            # the temp dir remains unless we delete it here. We intentionally delete only on success
            # by checking sys.exc_info in caller; simplest is to delete in an outer try/except.
            # Here we’re in finally; so only delete if no active exception.
            if sys.exc_info() == (None, None, None):
                shutil.rmtree(tmp_dir, ignore_errors=True)


def _main_inspect(cfg: ScriptConfig) -> int:
    if cfg.db_path is None:
        raise SystemExit("inspect mode requires --db")

    db_to_use = cfg.db_path
    temp_dir: Path | None = None

    print(f"Inspect source DB: {cfg.db_path}")
    _warn_if_other_db_has_more_sessions(cfg.db_path)

    if not cfg.no_copy:
        copied = _copy_db_for_inspection(cfg.db_path)
        temp_dir = copied.parent
        db_to_use = copied
        print(f"Inspect working copy DB: {db_to_use}")
    else:
        print(f"Inspect working DB (no copy): {db_to_use}")

    try:
        _set_db_env(db_to_use)

        from adaptive_tutor.storage.database import init_db

        # Safe even on a copy; ensures tables exist if DB was created but empty.
        init_db()

        if cfg.list_sessions is not None:
            sessions = _list_recent_sessions(cfg.list_sessions)
            print(json.dumps(sessions, indent=2, ensure_ascii=False))
            return 0

        if not cfg.session_id:
            raise SystemExit("inspect mode requires --session-id (or use --list-sessions N)")

        _validate_retrieval_ordering(cfg.session_id)
        _print_transcript(cfg.session_id)

        loaded = _validate_load_session_snapshot(cfg.session_id)
        _validate_runner_resume_from_db(cfg.session_id, expected=loaded)

        print("\n✅ Inspect mode validation passed")
        return 0
    finally:
        if cfg.keep_db:
            print(f"\nKeeping inspect DB copy at: {db_to_use}")
        else:
            if temp_dir is not None and sys.exc_info() == (None, None, None):
                shutil.rmtree(temp_dir, ignore_errors=True)


def _main_resume_child(session_id: str) -> int:
    # In child mode we MUST only print JSON to stdout.
    from adaptive_tutor.engine.runner import resume_session

    data = resume_session(session_id)
    sys.stdout.write(json.dumps(data, ensure_ascii=False))
    return 0


def main(argv: list[str]) -> int:
    ns = _parse_args(argv)

    if ns.resume_child:
        if not ns.session_id:
            raise SystemExit("--resume-child requires --session-id")
        return _main_resume_child(ns.session_id)

    cfg = _resolve_config(ns)

    if cfg.mode == "seed":
        return _main_seed(cfg)
    return _main_inspect(cfg)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
