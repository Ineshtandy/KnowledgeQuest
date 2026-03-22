import json

import pytest
from pydantic import ValidationError

from adaptive_tutor.agents import evaluator, planner, tutor
from adaptive_tutor.models.schemas import CurriculumPlan, EvaluationPayload, QuestionPayload, TeachingPayload


def test_planner_output_validates(monkeypatch):
    payload = {
        "topic": "linear algebra",
        "topic_summary": "core vector and matrix ideas",
        "assumed_user_level": "beginner",
        "levels": [
            {
                "level_index": 0,
                "title": "vectors",
                "goal": "understand vectors",
                "prerequisites": [],
                "success_criteria": "can add vectors",
                "remediation_focus": ["vector components"],
            },
            {
                "level_index": 1,
                "title": "dot product",
                "goal": "understand dot product",
                "prerequisites": ["vectors"],
                "success_criteria": "can compute dot product",
                "remediation_focus": ["projection intuition"],
            },
            {
                "level_index": 2,
                "title": "matrices",
                "goal": "understand matrix multiplication",
                "prerequisites": ["dot product"],
                "success_criteria": "can multiply small matrices",
                "remediation_focus": ["row-column rule"],
            },
            {
                "level_index": 3,
                "title": "linear systems",
                "goal": "solve small systems",
                "prerequisites": ["matrices"],
                "success_criteria": "solves 2x2 systems",
                "remediation_focus": ["elimination steps"],
            },
        ],
    }
    monkeypatch.setattr(planner, "_call_model", lambda _: json.dumps(payload))

    out = planner.create_curriculum("linear algebra")
    assert isinstance(out, CurriculumPlan)
    assert 4 <= len(out.levels) <= 8


def test_tutor_question_output_validates(monkeypatch):
    payload = {
        "question_id": "q1",
        "level_index": 0,
        "concept_title": "vectors",
        "question_type": "SHORT_ANSWER",
        "question_text": "What is a vector?",
        "expected_key_points": ["magnitude", "direction"],
        "hint": "Think geometry",
        "difficulty_note": "basic",
    }
    monkeypatch.setattr(tutor, "_call_model", lambda _: json.dumps(payload))

    level = CurriculumPlan(
        topic="linear algebra",
        topic_summary="summary",
        assumed_user_level="beginner",
        levels=[
            {
                "level_index": 0,
                "title": "vectors",
                "goal": "goal",
                "prerequisites": [],
                "success_criteria": "criteria",
                "remediation_focus": [],
            },
            {
                "level_index": 1,
                "title": "dot",
                "goal": "goal",
                "prerequisites": [],
                "success_criteria": "criteria",
                "remediation_focus": [],
            },
            {
                "level_index": 2,
                "title": "matrices",
                "goal": "goal",
                "prerequisites": [],
                "success_criteria": "criteria",
                "remediation_focus": [],
            },
            {
                "level_index": 3,
                "title": "systems",
                "goal": "goal",
                "prerequisites": [],
                "success_criteria": "criteria",
                "remediation_focus": [],
            },
        ],
    ).levels[0]

    out = tutor.generate_question("linear algebra", level, [], [])
    assert isinstance(out, QuestionPayload)


def test_evaluator_output_validates(monkeypatch):
    payload = {
        "question_id": "q1",
        "is_correct": False,
        "score": 0.2,
        "matched_key_points": ["magnitude"],
        "missing_key_points": ["direction"],
        "misconception_tag": "vector_definition",
        "feedback": "missing direction",
        "suggested_next_action": "TEACH",
    }
    monkeypatch.setattr(evaluator, "_call_model", lambda _: json.dumps(payload))

    level = CurriculumPlan(
        topic="linear algebra",
        topic_summary="summary",
        assumed_user_level="beginner",
        levels=[
            {"level_index": i, "title": str(i), "goal": "g", "prerequisites": [], "success_criteria": "s", "remediation_focus": []}
            for i in range(4)
        ],
    ).levels[0]
    question = QuestionPayload(
        question_id="q1",
        level_index=0,
        concept_title="vectors",
        question_type="SHORT_ANSWER",
        question_text="What is a vector?",
        expected_key_points=["magnitude", "direction"],
        hint="",
        difficulty_note="",
    )

    out = evaluator.evaluate_answer("linear algebra", level, question, "length only")
    assert isinstance(out, EvaluationPayload)


def test_teaching_output_validates(monkeypatch):
    payload = {
        "concept_title": "vectors",
        "summary": "vector includes direction",
        "why_user_was_wrong": "you omitted direction",
        "worked_example": "velocity as vector",
        "memory_tip": "arrow has size and direction",
        "checkpoint_question": "Is speed scalar or vector?",
    }
    monkeypatch.setattr(tutor, "_call_model", lambda _: json.dumps(payload))

    level = CurriculumPlan(
        topic="linear algebra",
        topic_summary="summary",
        assumed_user_level="beginner",
        levels=[
            {"level_index": i, "title": str(i), "goal": "g", "prerequisites": [], "success_criteria": "s", "remediation_focus": []}
            for i in range(4)
        ],
    ).levels[0]
    question = QuestionPayload(
        question_id="q1",
        level_index=0,
        concept_title="vectors",
        question_type="SHORT_ANSWER",
        question_text="What is a vector?",
        expected_key_points=["magnitude", "direction"],
        hint="hint",
        difficulty_note="basic",
    )
    evaluation_payload = EvaluationPayload(
        question_id="q1",
        is_correct=False,
        score=0.2,
        matched_key_points=["magnitude"],
        missing_key_points=["direction"],
        misconception_tag="vector_definition",
        feedback="missing direction",
        suggested_next_action="TEACH",
    )

    out = tutor.generate_teaching("linear algebra", level, question, evaluation_payload)
    assert isinstance(out, TeachingPayload)


def test_invalid_curriculum_fails_validation():
    with pytest.raises(ValidationError):
        CurriculumPlan(
            topic="x",
            topic_summary="x",
            assumed_user_level="x",
            levels=[
                {
                    "level_index": 0,
                    "title": "only one level",
                    "goal": "x",
                    "prerequisites": [],
                    "success_criteria": "x",
                    "remediation_focus": [],
                }
            ],
        )
