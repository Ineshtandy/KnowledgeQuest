from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from adaptive_tutor.workflow.nodes import (
    await_user_answer_node,
    evaluate_answer_node,
    finish_session_node,
    generate_question_node,
    plan_curriculum_node,
    teach_if_needed_node,
    update_progress_node,
)
from adaptive_tutor.workflow.routers import route_after_progress
from adaptive_tutor.workflow.state import WorkflowState


def build_graph():
    builder = StateGraph(WorkflowState)

    builder.add_node("plan_curriculum", plan_curriculum_node)
    builder.add_node("generate_question", generate_question_node)
    builder.add_node("await_user_answer", await_user_answer_node)
    builder.add_node("evaluate_answer", evaluate_answer_node)
    builder.add_node("update_progress", update_progress_node)
    builder.add_node("teach_if_needed", teach_if_needed_node)
    builder.add_node("finish_session", finish_session_node)

    builder.add_edge(START, "plan_curriculum")
    builder.add_edge("plan_curriculum", "generate_question")
    builder.add_edge("generate_question", "await_user_answer")
    builder.add_edge("await_user_answer", "evaluate_answer")
    builder.add_edge("evaluate_answer", "update_progress")
    builder.add_conditional_edges(
        "update_progress",
        route_after_progress,
        {
            "generate_question": "generate_question",
            "teach_if_needed": "teach_if_needed",
            "finish_session": "finish_session",
        },
    )
    builder.add_edge("teach_if_needed", "generate_question")
    builder.add_edge("finish_session", END)

    return builder
