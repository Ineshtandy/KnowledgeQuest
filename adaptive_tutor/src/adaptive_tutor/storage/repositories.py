from __future__ import annotations

import json

from sqlalchemy import desc, select

from adaptive_tutor.models.db_models import AttemptDB, SessionDB, TeachingDB
from adaptive_tutor.models.enums import SessionStatus
from adaptive_tutor.storage.database import session_scope


def create_session(topic: str, curriculum_json: str | None = None) -> SessionDB:
    with session_scope() as session:
        row = SessionDB(topic=topic, status=SessionStatus.NEW.value, curriculum_json=curriculum_json)
        session.add(row)
        session.flush()
        session.refresh(row)
        return row


def get_session(session_id: str) -> SessionDB | None:
    with session_scope() as session:
        return session.get(SessionDB, session_id)


def update_session_progress(session_id: str, current_level_index: int, status: str) -> None:
    with session_scope() as session:
        row = session.get(SessionDB, session_id)
        if row is None:
            return
        row.current_level_index = current_level_index
        row.status = status


def save_curriculum(session_id: str, curriculum_json: str) -> None:
    with session_scope() as session:
        row = session.get(SessionDB, session_id)
        if row is None:
            return
        row.curriculum_json = curriculum_json


def mark_session_completed(session_id: str) -> None:
    with session_scope() as session:
        row = session.get(SessionDB, session_id)
        if row is None:
            return
        row.status = SessionStatus.COMPLETED.value


def create_attempt(
    session_id: str,
    level_index: int,
    question_id: str,
    question_text: str,
    question_type: str,
    expected_key_points: list[str],
    user_answer: str,
    is_correct: bool,
    score: float,
    misconception_tag: str | None,
    feedback: str,
    next_action: str,
) -> AttemptDB:
    with session_scope() as session:
        row = AttemptDB(
            session_id=session_id,
            level_index=level_index,
            question_id=question_id,
            question_text=question_text,
            question_type=question_type,
            expected_key_points_json=json.dumps(expected_key_points),
            user_answer=user_answer,
            is_correct=is_correct,
            score=score,
            misconception_tag=misconception_tag,
            feedback=feedback,
            next_action=next_action,
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        return row


def list_attempts_for_session(session_id: str) -> list[AttemptDB]:
    with session_scope() as session:
        result = session.execute(
            select(AttemptDB).where(AttemptDB.session_id == session_id).order_by(AttemptDB.created_at.asc())
        )
        return list(result.scalars().all())


def list_attempts_for_level(session_id: str, level_index: int) -> list[AttemptDB]:
    with session_scope() as session:
        result = session.execute(
            select(AttemptDB)
            .where(AttemptDB.session_id == session_id, AttemptDB.level_index == level_index)
            .order_by(AttemptDB.created_at.asc())
        )
        return list(result.scalars().all())


def get_recent_attempts(session_id: str, limit: int = 5) -> list[AttemptDB]:
    with session_scope() as session:
        result = session.execute(
            select(AttemptDB)
            .where(AttemptDB.session_id == session_id)
            .order_by(desc(AttemptDB.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())


def create_teaching(
    session_id: str,
    level_index: int,
    question_id: str,
    summary: str,
    why_user_was_wrong: str,
    worked_example: str,
    memory_tip: str,
    checkpoint_question: str,
) -> TeachingDB:
    with session_scope() as session:
        row = TeachingDB(
            session_id=session_id,
            level_index=level_index,
            question_id=question_id,
            summary=summary,
            why_user_was_wrong=why_user_was_wrong,
            worked_example=worked_example,
            memory_tip=memory_tip,
            checkpoint_question=checkpoint_question,
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        return row


def list_teachings_for_session(session_id: str) -> list[TeachingDB]:
    with session_scope() as session:
        result = session.execute(
            select(TeachingDB).where(TeachingDB.session_id == session_id).order_by(TeachingDB.created_at.asc())
        )
        return list(result.scalars().all())
