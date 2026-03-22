from __future__ import annotations

import json

from google import genai

from adaptive_tutor.config import settings
from adaptive_tutor.models.schemas import EvaluationPayload, LevelPlan, QuestionPayload, TeachingPayload

from .prompts import TUTOR_QUESTION_PROMPT, TUTOR_TEACHING_PROMPT


def _call_model(prompt: str) -> str:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(model=settings.GEMINI_MODEL, contents=prompt)
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini returned empty response text")
    return text


def _extract_json(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[len("json") :].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in model output")
    return stripped[start : end + 1]


def generate_question(
    topic: str,
    level: LevelPlan,
    recent_attempts: list,
    misconception_history: list[str],
) -> QuestionPayload:
    prompt = TUTOR_QUESTION_PROMPT.format(
        topic=topic,
        level_json=level.model_dump_json(),
        recent_attempts_json=json.dumps(recent_attempts),
        misconceptions_json=json.dumps(misconception_history),
    )
    text = _call_model(prompt)
    payload = json.loads(_extract_json(text))
    question = QuestionPayload.model_validate(payload)
    return question


def generate_teaching(
    topic: str,
    level: LevelPlan,
    question: QuestionPayload,
    evaluation: EvaluationPayload,
) -> TeachingPayload:
    prompt = TUTOR_TEACHING_PROMPT.format(
        topic=topic,
        level_json=level.model_dump_json(),
        question_json=question.model_dump_json(),
        evaluation_json=evaluation.model_dump_json(),
    )
    text = _call_model(prompt)
    payload = json.loads(_extract_json(text))
    teaching = TeachingPayload.model_validate(payload)
    return teaching
