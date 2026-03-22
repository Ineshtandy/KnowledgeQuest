from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from adaptive_tutor.engine.session_manager import create_new_session, load_session
from adaptive_tutor.storage.database import init_db
from adaptive_tutor.workflow.graph import build_graph


init_db()
_graph = build_graph().compile(checkpointer=InMemorySaver())


def _thread_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _maybe_model_dump(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    dump_fn = getattr(value, "model_dump", None)
    if callable(dump_fn):
        return dump_fn()
    return None


def _extract_interrupt_question(result: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__", [])
    if not interrupts:
        return None
    first = interrupts[0]
    value = getattr(first, "value", first)
    if isinstance(value, dict) and "question" in value:
        return value["question"]
    return None


def _compose_display_text(
    *,
    question: dict[str, Any] | None,
    evaluation: dict[str, Any] | None,
    teaching: dict[str, Any] | None,
    session_complete: bool,
) -> str:
    parts: list[str] = []

    if evaluation and evaluation.get("feedback"):
        parts.append(str(evaluation.get("feedback")))

    if teaching:
        summary = teaching.get("summary")
        worked_example = teaching.get("worked_example")
        memory_tip = teaching.get("memory_tip")
        checkpoint_question = teaching.get("checkpoint_question")
        if summary:
            parts.append(f"Teaching: {summary}")
        if worked_example:
            parts.append(f"Example: {worked_example}")
        if memory_tip:
            parts.append(f"Tip: {memory_tip}")
        if checkpoint_question:
            parts.append(f"Checkpoint: {checkpoint_question}")

    if question and question.get("question_text"):
        parts.append(f"Question: {question['question_text']}")

    if session_complete:
        parts.append("Session complete.")

    return "\n\n".join([p for p in parts if p]).strip() or ""


def _build_ui_events(
    *,
    evaluation: dict[str, Any] | None,
    next_action: str | None,
    teaching: dict[str, Any] | None,
    question_present: bool,
    is_session_start: bool,
    session_complete: bool,
) -> list[str]:
    events: list[str] = []

    if is_session_start:
        events.extend(["session_started", "curriculum_planned"])
    else:
        events.append("answer_submitted")
        if evaluation is not None and "is_correct" in evaluation:
            if bool(evaluation.get("is_correct")):
                events.append("answer_correct")
            else:
                events.append("answer_incorrect")

    if session_complete or (next_action == "FINISH"):
        events.append("session_finished")
    elif next_action == "TEACH" and teaching is not None:
        events.append("teaching_started")
    elif next_action == "ADVANCE":
        events.append("level_advanced")
    elif next_action == "DEMOTE":
        events.append("level_demoted")

    if question_present and not session_complete and next_action != "FINISH":
        events.append("question_presented")

    events.append("state_synced")
    return events


def start_session(topic: str) -> dict:
    session_id = create_new_session(topic)
    initial_state = {
        "session_id": session_id,
        "topic": topic,
        "curriculum": None,
        "current_level_index": 0,
        "current_question": None,
        "last_user_answer": None,
        "last_evaluation": None,
        "current_teaching": None,
        "questions_asked_in_level": 0,
        "correct_count_in_level": 0,
        "incorrect_count_in_level": 0,
        "consecutive_wrong_count": 0,
        "misconception_history": [],
        "next_action": None,
        "session_complete": False,
    }

    result = _graph.invoke(initial_state, config=_thread_config(session_id))
    question = _extract_interrupt_question(result)
    if question is None:
        state = _graph.get_state(_thread_config(session_id)).values
        question_obj = state.get("current_question")
        question = question_obj.model_dump() if question_obj else None

    display_text = _compose_display_text(
        question=question,
        evaluation=None,
        teaching=None,
        session_complete=False,
    )

    return {
        "session_id": session_id,
        "topic": topic,
        "question": question,
        "session_complete": False,
        "display_text": display_text,
        "input_mode": "answer",
        "ui_events": _build_ui_events(
            evaluation=None,
            next_action=None,
            teaching=None,
            question_present=question is not None,
            is_session_start=True,
            session_complete=False,
        ),
    }


def resume_session(session_id: str) -> dict:
    snapshot = _graph.get_state(_thread_config(session_id))
    state = snapshot.values or {}

    if not state:
        loaded = load_session(session_id)
        if loaded is None:
            raise ValueError("Session not found")
        state = loaded.model_dump()

    question_obj = state.get("current_question")
    teaching_obj = state.get("current_teaching")
    evaluation_obj = state.get("last_evaluation")

    return {
        "session_id": session_id,
        "topic": state.get("topic"),
        "question": _maybe_model_dump(question_obj),
        "teaching": _maybe_model_dump(teaching_obj),
        "evaluation": _maybe_model_dump(evaluation_obj),
        "session_complete": state.get("session_complete", False),
        "next_action": state.get("next_action"),
        "current_level_index": state.get("current_level_index", 0),
    }


def submit_answer(session_id: str, answer: str) -> dict:
    result = _graph.invoke(Command(resume={"answer": answer}), config=_thread_config(session_id))

    question = _extract_interrupt_question(result)

    snapshot = _graph.get_state(_thread_config(session_id))
    state = snapshot.values

    evaluation_obj = state.get("last_evaluation")
    teaching_obj = state.get("current_teaching")

    if question is None:
        question_obj = state.get("current_question")
        question = question_obj.model_dump() if question_obj else None

    session_complete = bool(state.get("session_complete", False))
    next_action = state.get("next_action")
    evaluation = evaluation_obj.model_dump() if evaluation_obj else None
    teaching = teaching_obj.model_dump() if teaching_obj else None
    display_text = _compose_display_text(
        question=question,
        evaluation=evaluation,
        teaching=teaching,
        session_complete=session_complete,
    )

    return {
        "session_id": session_id,
        "evaluation": evaluation,
        "teaching": teaching,
        "next_question": question,
        "session_complete": session_complete,
        "next_action": next_action,
        "current_level_index": state.get("current_level_index", 0),
        "display_text": display_text,
        "input_mode": "session_complete" if session_complete else "answer",
        "ui_events": _build_ui_events(
            evaluation=evaluation,
            next_action=next_action,
            teaching=teaching,
            question_present=question is not None,
            is_session_start=False,
            session_complete=session_complete,
        ),
    }
