from adaptive_tutor.models.enums import NextAction


def route_after_progress(state: dict) -> str:
    if state.get("session_complete"):
        return "finish_session"
    if state.get("next_action") == NextAction.TEACH.value:
        return "teach_if_needed"
    return "generate_question"
