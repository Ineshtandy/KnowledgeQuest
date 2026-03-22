from __future__ import annotations

import json

from google import genai

from adaptive_tutor.config import settings
from adaptive_tutor.models.schemas import CurriculumPlan

from .prompts import PLANNER_PROMPT


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


def create_curriculum(topic: str) -> CurriculumPlan:
    prompt = PLANNER_PROMPT.format(topic=topic)
    text = _call_model(prompt)
    json_payload = _extract_json(text)
    data = json.loads(json_payload)
    curriculum = CurriculumPlan.model_validate(data)
    return curriculum
