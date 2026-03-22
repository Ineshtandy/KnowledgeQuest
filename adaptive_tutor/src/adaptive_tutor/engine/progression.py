from adaptive_tutor.models.enums import NextAction


def apply_evaluation_to_progress(
    correct_count: int,
    incorrect_count: int,
    consecutive_wrong_count: int,
    evaluation_is_correct: bool,
) -> tuple[int, int, int]:
    if evaluation_is_correct:
        return correct_count + 1, incorrect_count, 0
    return correct_count, incorrect_count + 1, consecutive_wrong_count + 1


def decide_next_action(
    questions_asked_in_level: int,
    correct_count_in_level: int,
    consecutive_wrong_count: int,
    total_levels: int,
    current_level_index: int,
    pass_threshold: int,
    questions_per_level: int,
    wrong_threshold_for_teaching: int,
) -> str:
    if consecutive_wrong_count >= wrong_threshold_for_teaching:
        return NextAction.TEACH.value

    passed_level = correct_count_in_level >= pass_threshold
    exhausted_level_questions = questions_asked_in_level >= questions_per_level

    if passed_level:
        if current_level_index >= total_levels - 1:
            return NextAction.FINISH.value
        return NextAction.ADVANCE.value

    if exhausted_level_questions:
        if current_level_index > 0:
            return NextAction.DEMOTE.value
        return NextAction.CONTINUE.value

    return NextAction.CONTINUE.value
