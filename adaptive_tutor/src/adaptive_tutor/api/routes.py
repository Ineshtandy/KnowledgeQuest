from fastapi import APIRouter, HTTPException

from adaptive_tutor.api.schemas import (
    AnswerResponse,
    CreateSessionRequest,
    QuestionResponse,
    SessionResponse,
    SubmitAnswerRequest,
)
from adaptive_tutor.engine.runner import resume_session, start_session, submit_answer


router = APIRouter()


@router.post("/sessions", response_model=QuestionResponse)
def create_session(payload: CreateSessionRequest) -> QuestionResponse:
    result = start_session(payload.topic)
    return QuestionResponse.model_validate(result)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    try:
        state = resume_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SessionResponse(
        session_id=session_id,
        topic=state.get("topic") or "",
        current_level_index=state.get("current_level_index", 0),
        session_complete=state.get("session_complete", False),
        next_action=state.get("next_action"),
    )


@router.post("/sessions/{session_id}/answer", response_model=AnswerResponse)
def answer_session(session_id: str, payload: SubmitAnswerRequest) -> AnswerResponse:
    try:
        result = submit_answer(session_id=session_id, answer=payload.answer)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return AnswerResponse.model_validate(result)
