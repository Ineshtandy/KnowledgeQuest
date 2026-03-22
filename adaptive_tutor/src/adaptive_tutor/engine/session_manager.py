from __future__ import annotations

import json

from adaptive_tutor.models.enums import SessionStatus
from adaptive_tutor.models.schemas import CurriculumPlan, EvaluationPayload, GraphState, QuestionPayload, TeachingPayload
from adaptive_tutor.storage import repositories


def create_new_session(topic: str) -> str:
    row = repositories.create_session(topic=topic)
    return row.id


def load_session(session_id: str) -> GraphState | None:
    session_row = repositories.get_session(session_id)
    if session_row is None:
        return None

    curriculum = None
    if session_row.curriculum_json:
        curriculum = CurriculumPlan.model_validate_json(session_row.curriculum_json)

    attempts = repositories.list_attempts_for_session(session_id)
    teachings = repositories.list_teachings_for_session(session_id)

    level_attempts = [a for a in attempts if a.level_index == session_row.current_level_index]
    correct_count = sum(1 for a in level_attempts if a.is_correct)
    incorrect_count = sum(1 for a in level_attempts if not a.is_correct)

    consecutive_wrong = 0
    for attempt in reversed(level_attempts):
        if attempt.is_correct:
            break
        consecutive_wrong += 1

    last_attempt = attempts[-1] if attempts else None
    last_eval = None
    last_answer = None
    current_question = None
    if last_attempt is not None:
        last_answer = last_attempt.user_answer
        current_question = QuestionPayload(
            question_id=last_attempt.question_id,
            level_index=last_attempt.level_index,
            concept_title="",
            question_type=last_attempt.question_type,
            question_text=last_attempt.question_text,
            expected_key_points=json.loads(last_attempt.expected_key_points_json),
            hint="",
            difficulty_note="",
        )
        last_eval = EvaluationPayload(
            question_id=last_attempt.question_id,
            is_correct=last_attempt.is_correct,
            score=last_attempt.score,
            matched_key_points=[],
            missing_key_points=[],
            misconception_tag=last_attempt.misconception_tag,
            feedback=last_attempt.feedback,
            suggested_next_action=last_attempt.next_action,
        )

    current_teaching = None
    if teachings:
        t = teachings[-1]
        current_teaching = TeachingPayload(
            # Attempt rows do not currently persist concept_title, so use a stable fallback.
            concept_title="Recovered concept",
            summary=t.summary,
            why_user_was_wrong=t.why_user_was_wrong,
            worked_example=t.worked_example,
            memory_tip=t.memory_tip,
            checkpoint_question=t.checkpoint_question,
        )

    return GraphState(
        session_id=session_row.id,
        topic=session_row.topic,
        curriculum=curriculum,
        current_level_index=session_row.current_level_index,
        current_question=current_question,
        last_user_answer=last_answer,
        last_evaluation=last_eval,
        current_teaching=current_teaching,
        questions_asked_in_level=len(level_attempts),
        correct_count_in_level=correct_count,
        incorrect_count_in_level=incorrect_count,
        consecutive_wrong_count=consecutive_wrong,
        misconception_history=[a.misconception_tag for a in attempts if a.misconception_tag],
        next_action=last_attempt.next_action if last_attempt else None,
        session_complete=session_row.status == SessionStatus.COMPLETED.value,
    )


def save_curriculum_for_session(session_id: str, curriculum: CurriculumPlan) -> None:
    repositories.save_curriculum(session_id=session_id, curriculum_json=curriculum.model_dump_json())
    repositories.update_session_progress(
        session_id=session_id,
        current_level_index=0,
        status=SessionStatus.ACTIVE.value,
    )


def save_attempt_for_session(
    session_id: str,
    level_index: int,
    question: QuestionPayload,
    user_answer: str,
    evaluation: EvaluationPayload,
    next_action: str,
) -> None:
    repositories.create_attempt(
        session_id=session_id,
        level_index=level_index,
        question_id=question.question_id,
        question_text=question.question_text,
        question_type=question.question_type,
        expected_key_points=question.expected_key_points,
        user_answer=user_answer,
        is_correct=evaluation.is_correct,
        score=evaluation.score,
        misconception_tag=evaluation.misconception_tag,
        feedback=evaluation.feedback,
        next_action=next_action,
    )


def save_teaching_for_session(
    session_id: str,
    level_index: int,
    question_id: str,
    teaching: TeachingPayload,
) -> None:
    repositories.create_teaching(
        session_id=session_id,
        level_index=level_index,
        question_id=question_id,
        summary=teaching.summary,
        why_user_was_wrong=teaching.why_user_was_wrong,
        worked_example=teaching.worked_example,
        memory_tip=teaching.memory_tip,
        checkpoint_question=teaching.checkpoint_question,
    )


def save_session_progress(session_id: str, current_level_index: int, status: SessionStatus) -> None:
    repositories.update_session_progress(
        session_id=session_id,
        current_level_index=current_level_index,
        status=status.value,
    )


def mark_session_complete(session_id: str, current_level_index: int) -> None:
    repositories.update_session_progress(
        session_id=session_id,
        current_level_index=current_level_index,
        status=SessionStatus.COMPLETED.value,
    )
