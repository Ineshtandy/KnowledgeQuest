import json

from adaptive_tutor.models.enums import SessionStatus
from adaptive_tutor.models.schemas import CurriculumPlan, EvaluationPayload, QuestionPayload, TeachingPayload
from adaptive_tutor.storage.database import init_db, session_scope
from adaptive_tutor.storage.repositories import (
    AttemptDB,
    SessionDB,
    TeachingDB,
    create_session,
    get_session,
    list_attempts_for_session,
    list_teachings_for_session,
)
from adaptive_tutor.engine import session_manager


def _clear_db():
    with session_scope() as s:
        s.query(AttemptDB).delete()
        s.query(TeachingDB).delete()
        s.query(SessionDB).delete()


def test_new_session_created():
    init_db()
    _clear_db()
    row = create_session("python basics")
    loaded = get_session(row.id)
    assert loaded is not None
    assert loaded.topic == "python basics"


def test_curriculum_saved():
    init_db()
    _clear_db()
    sid = session_manager.create_new_session("python")
    curriculum = CurriculumPlan(
        topic="python",
        topic_summary="summary",
        assumed_user_level="beginner",
        levels=[
            {"level_index": i, "title": str(i), "goal": "g", "prerequisites": [], "success_criteria": "s", "remediation_focus": []}
            for i in range(4)
        ],
    )
    session_manager.save_curriculum_for_session(sid, curriculum)
    loaded = get_session(sid)
    assert loaded is not None
    assert loaded.curriculum_json is not None
    assert json.loads(loaded.curriculum_json)["topic"] == "python"
    assert loaded.status == SessionStatus.ACTIVE.value


def test_attempts_persisted():
    init_db()
    _clear_db()
    sid = session_manager.create_new_session("python")
    q = QuestionPayload(
        question_id="q1",
        level_index=0,
        concept_title="variables",
        question_type="SHORT_ANSWER",
        question_text="What is a variable?",
        expected_key_points=["name", "value"],
        hint="",
        difficulty_note="",
    )
    e = EvaluationPayload(
        question_id="q1",
        is_correct=True,
        score=1.0,
        matched_key_points=["name", "value"],
        missing_key_points=[],
        misconception_tag=None,
        feedback="good",
        suggested_next_action="CONTINUE",
    )
    session_manager.save_attempt_for_session(sid, 0, q, "storage", e, "CONTINUE")
    attempts = list_attempts_for_session(sid)
    assert len(attempts) == 1
    assert attempts[0].question_id == "q1"


def test_teachings_persisted():
    init_db()
    _clear_db()
    sid = session_manager.create_new_session("python")
    t = TeachingPayload(
        concept_title="variables",
        summary="a variable stores a value",
        why_user_was_wrong="you confused with function",
        worked_example="x = 5",
        memory_tip="box label and item",
        checkpoint_question="What does y = 3 do?",
    )
    session_manager.save_teaching_for_session(sid, 0, "q1", t)
    teachings = list_teachings_for_session(sid)
    assert len(teachings) == 1
    assert teachings[0].question_id == "q1"


def test_completed_status_stored():
    init_db()
    _clear_db()
    sid = session_manager.create_new_session("python")
    session_manager.mark_session_complete(sid, 2)
    loaded = get_session(sid)
    assert loaded is not None
    assert loaded.status == SessionStatus.COMPLETED.value
