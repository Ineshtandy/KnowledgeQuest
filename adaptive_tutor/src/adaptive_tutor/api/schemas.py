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
    display_text: str
    input_mode: str
    ui_events: list[str] = Field(default_factory=list)
    display_text: str
    input_mode: str
    ui_events: list[str] = Field(default_factory=list)


class AnswerResponse(BaseModel):
    session_id: str
    evaluation: dict | None
    teaching: dict | None
    next_question: dict | None
    session_complete: bool
    next_action: str | None = None
    current_level_index: int = 0
    display_text: str
    input_mode: str
    ui_events: list[str] = Field(default_factory=list)
    display_text: str
    input_mode: str
    ui_events: list[str] = Field(default_factory=list)
