from enum import StrEnum


class SessionStatus(StrEnum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"


class QuestionType(StrEnum):
    SHORT_ANSWER = "SHORT_ANSWER"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"
    SCENARIO = "SCENARIO"


class NextAction(StrEnum):
    CONTINUE = "CONTINUE"
    TEACH = "TEACH"
    ADVANCE = "ADVANCE"
    DEMOTE = "DEMOTE"
    FINISH = "FINISH"
