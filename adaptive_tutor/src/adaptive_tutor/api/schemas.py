from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    topic: str = Field(min_length=1)


class SubmitAnswerRequest(BaseModel):
    answer: str = Field(min_length=1)


class SessionResponse(BaseModel):
    session_id: str
    topic: str
    current_level_index: int = 0
    session_complete: bool
    next_action: str | None = None


class QuestionResponse(BaseModel):
    session_id: str
    topic: str
    question: dict | None
    session_complete: bool


class AnswerResponse(BaseModel):
    session_id: str
    evaluation: dict | None
    teaching: dict | None
    next_question: dict | None
    session_complete: bool
    next_action: str | None = None
    current_level_index: int = 0
