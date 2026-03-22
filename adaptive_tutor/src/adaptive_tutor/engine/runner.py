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


def _extract_interrupt_question(result: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__", [])
    if not interrupts:
        return None
    first = interrupts[0]
    value = getattr(first, "value", first)
    if isinstance(value, dict) and "question" in value:
        return value["question"]
    return None


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

    return {
        "session_id": session_id,
        "topic": topic,
        "question": question,
        "session_complete": False,
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
        "question": question_obj.model_dump() if question_obj else None,
        "teaching": teaching_obj.model_dump() if teaching_obj else None,
        "evaluation": evaluation_obj.model_dump() if evaluation_obj else None,
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

    return {
        "session_id": session_id,
        "evaluation": evaluation_obj.model_dump() if evaluation_obj else None,
        "teaching": teaching_obj.model_dump() if teaching_obj else None,
        "next_question": question,
        "session_complete": state.get("session_complete", False),
        "next_action": state.get("next_action"),
        "current_level_index": state.get("current_level_index", 0),
    }
