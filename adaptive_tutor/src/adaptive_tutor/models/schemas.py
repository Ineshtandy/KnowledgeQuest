from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class LevelPlan(BaseModel):
    level_index: int = Field(ge=0)
    title: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    prerequisites: list[str] = Field(default_factory=list)
    success_criteria: str = Field(min_length=1)
    remediation_focus: list[str] = Field(default_factory=list)


class CurriculumPlan(BaseModel):
    topic: str = Field(min_length=1)
    topic_summary: str = Field(min_length=1)
    assumed_user_level: str = Field(min_length=1)
    levels: list[LevelPlan]

    @model_validator(mode="after")
    def validate_levels(self) -> "CurriculumPlan":
        if not (4 <= len(self.levels) <= 8):
            raise ValueError("Curriculum must contain between 4 and 8 levels")
        for idx, level in enumerate(self.levels):
            if level.level_index != idx:
                raise ValueError("Level indexes must be contiguous and zero-based")
        return self


class QuestionPayload(BaseModel):
    question_id: str = Field(min_length=1)
    level_index: int = Field(ge=0)
    concept_title: str
    question_type: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    expected_key_points: list[str] = Field(default_factory=list)
    hint: str
    difficulty_note: str


class EvaluationPayload(BaseModel):
    question_id: str = Field(min_length=1)
    is_correct: bool
    score: float = Field(ge=0.0, le=1.0)
    matched_key_points: list[str] = Field(default_factory=list)
    missing_key_points: list[str] = Field(default_factory=list)
    misconception_tag: Optional[str] = None
    feedback: str = Field(min_length=1)
    suggested_next_action: str = Field(min_length=1)


class TeachingPayload(BaseModel):
    concept_title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    why_user_was_wrong: str = Field(min_length=1)
    worked_example: str = Field(min_length=1)
    memory_tip: str = Field(min_length=1)
    checkpoint_question: str = Field(min_length=1)


class GraphState(BaseModel):
    session_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    curriculum: Optional[CurriculumPlan] = None
    current_level_index: int = Field(default=0, ge=0)
    current_question: Optional[QuestionPayload] = None
    last_user_answer: Optional[str] = None
    last_evaluation: Optional[EvaluationPayload] = None
    current_teaching: Optional[TeachingPayload] = None
    questions_asked_in_level: int = Field(default=0, ge=0)
    correct_count_in_level: int = Field(default=0, ge=0)
    incorrect_count_in_level: int = Field(default=0, ge=0)
    consecutive_wrong_count: int = Field(default=0, ge=0)
    misconception_history: list[str] = Field(default_factory=list)
    next_action: Optional[str] = None
    session_complete: bool = False

    @field_validator("last_user_answer")
    @classmethod
    def normalize_answer(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None
