from __future__ import annotations

from typing import TypedDict

from adaptive_tutor.models.schemas import CurriculumPlan, EvaluationPayload, QuestionPayload, TeachingPayload


class WorkflowState(TypedDict):
    session_id: str
    topic: str
    curriculum: CurriculumPlan | None
    current_level_index: int
    current_question: QuestionPayload | None
    last_user_answer: str | None
    last_evaluation: EvaluationPayload | None
    current_teaching: TeachingPayload | None
    questions_asked_in_level: int
    correct_count_in_level: int
    incorrect_count_in_level: int
    consecutive_wrong_count: int
    misconception_history: list[str]
    next_action: str | None
    session_complete: bool
