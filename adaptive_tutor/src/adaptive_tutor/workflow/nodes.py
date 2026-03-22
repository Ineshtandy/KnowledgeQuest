from __future__ import annotations

from langgraph.types import interrupt

from adaptive_tutor.agents.evaluator import evaluate_answer
from adaptive_tutor.agents.planner import create_curriculum
from adaptive_tutor.agents.tutor import generate_question, generate_teaching
from adaptive_tutor.config import settings
from adaptive_tutor.engine.misconception_tracker import update_history
from adaptive_tutor.engine.progression import apply_evaluation_to_progress, decide_next_action
from adaptive_tutor.engine.session_manager import (
    mark_session_complete,
    save_attempt_for_session,
    save_curriculum_for_session,
    save_session_progress,
    save_teaching_for_session,
)
from adaptive_tutor.models.enums import NextAction, SessionStatus
from adaptive_tutor.storage.repositories import get_recent_attempts


def plan_curriculum_node(state: dict) -> dict:
    if state.get("curriculum") is not None:
        return {}
    curriculum = create_curriculum(state["topic"])
    save_curriculum_for_session(state["session_id"], curriculum)
    return {"curriculum": curriculum}


def generate_question_node(state: dict) -> dict:
    curriculum = state.get("curriculum")
    if curriculum is None:
        raise ValueError("Cannot generate question without curriculum")
    level = curriculum.levels[state["current_level_index"]]
    attempts = get_recent_attempts(state["session_id"], limit=5)
    recent_attempts = [
        {
            "question_id": a.question_id,
            "question_text": a.question_text,
            "is_correct": a.is_correct,
            "misconception_tag": a.misconception_tag,
            "score": a.score,
        }
        for a in attempts
    ]
    question = generate_question(
        topic=state["topic"],
        level=level,
        recent_attempts=recent_attempts,
        misconception_history=state.get("misconception_history", []),
    )
    return {"current_question": question}


def await_user_answer_node(state: dict) -> dict:
    question = state.get("current_question")
    if question is None:
        raise ValueError("No current question to present")
    answer_payload = interrupt({"question": question.model_dump()})
    if isinstance(answer_payload, dict):
        answer = answer_payload.get("answer")
    else:
        answer = str(answer_payload)
    return {"last_user_answer": answer}


def evaluate_answer_node(state: dict) -> dict:
    curriculum = state.get("curriculum")
    question = state.get("current_question")
    answer = state.get("last_user_answer")
    if curriculum is None or question is None or not answer:
        raise ValueError("Evaluation requires curriculum, question, and answer")

    level = curriculum.levels[state["current_level_index"]]
    evaluation = evaluate_answer(
        topic=state["topic"],
        level=level,
        question=question,
        user_answer=answer,
    )

    return {"last_evaluation": evaluation}


def update_progress_node(state: dict) -> dict:
    evaluation = state.get("last_evaluation")
    question = state.get("current_question")
    answer = state.get("last_user_answer")
    curriculum = state.get("curriculum")
    if evaluation is None or question is None or answer is None or curriculum is None:
        raise ValueError("Progress update requires evaluation, question, answer, and curriculum")

    questions_asked = state["questions_asked_in_level"] + 1
    correct_count, incorrect_count, consecutive_wrong = apply_evaluation_to_progress(
        correct_count=state["correct_count_in_level"],
        incorrect_count=state["incorrect_count_in_level"],
        consecutive_wrong_count=state["consecutive_wrong_count"],
        evaluation_is_correct=evaluation.is_correct,
    )

    next_action = decide_next_action(
        questions_asked_in_level=questions_asked,
        correct_count_in_level=correct_count,
        consecutive_wrong_count=consecutive_wrong,
        total_levels=len(curriculum.levels),
        current_level_index=state["current_level_index"],
        pass_threshold=settings.PASS_THRESHOLD,
        questions_per_level=settings.QUESTIONS_PER_LEVEL,
        wrong_threshold_for_teaching=settings.CONSECUTIVE_WRONG_FOR_TEACHING,
    )

    save_attempt_for_session(
        session_id=state["session_id"],
        level_index=state["current_level_index"],
        question=question,
        user_answer=answer,
        evaluation=evaluation,
        next_action=next_action,
    )

    updated_level_index = state["current_level_index"]
    updated_questions = questions_asked
    updated_correct = correct_count
    updated_incorrect = incorrect_count

    if next_action == NextAction.ADVANCE.value:
        updated_level_index += 1
        updated_questions = 0
        updated_correct = 0
        updated_incorrect = 0
        consecutive_wrong = 0
    elif next_action == NextAction.DEMOTE.value:
        updated_level_index = max(0, updated_level_index - 1)
        updated_questions = 0
        updated_correct = 0
        updated_incorrect = 0
        consecutive_wrong = 0
    elif next_action == NextAction.FINISH.value:
        mark_session_complete(state["session_id"], updated_level_index)
        return {
            "session_complete": True,
            "next_action": next_action,
            "questions_asked_in_level": updated_questions,
            "correct_count_in_level": updated_correct,
            "incorrect_count_in_level": updated_incorrect,
            "consecutive_wrong_count": consecutive_wrong,
            "misconception_history": update_history(
                state.get("misconception_history", []),
                evaluation.misconception_tag,
            ),
        }

    save_session_progress(state["session_id"], updated_level_index, SessionStatus.ACTIVE)

    return {
        "current_level_index": updated_level_index,
        "questions_asked_in_level": updated_questions,
        "correct_count_in_level": updated_correct,
        "incorrect_count_in_level": updated_incorrect,
        "consecutive_wrong_count": consecutive_wrong,
        "misconception_history": update_history(
            state.get("misconception_history", []),
            evaluation.misconception_tag,
        ),
        "next_action": next_action,
        "current_teaching": None if next_action != NextAction.TEACH.value else state.get("current_teaching"),
    }


def teach_if_needed_node(state: dict) -> dict:
    curriculum = state.get("curriculum")
    question = state.get("current_question")
    evaluation = state.get("last_evaluation")
    if curriculum is None or question is None or evaluation is None:
        raise ValueError("Teaching requires curriculum, question, and evaluation")

    level = curriculum.levels[state["current_level_index"]]
    teaching = generate_teaching(
        topic=state["topic"],
        level=level,
        question=question,
        evaluation=evaluation,
    )

    save_teaching_for_session(
        session_id=state["session_id"],
        level_index=state["current_level_index"],
        question_id=question.question_id,
        teaching=teaching,
    )

    return {"current_teaching": teaching}


def finish_session_node(state: dict) -> dict:
    mark_session_complete(state["session_id"], state["current_level_index"])
    return {"session_complete": True, "next_action": NextAction.FINISH.value}
