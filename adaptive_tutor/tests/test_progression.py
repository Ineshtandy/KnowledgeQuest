from adaptive_tutor.engine.progression import decide_next_action
from adaptive_tutor.models.enums import NextAction


def test_four_of_five_correct_advances():
    out = decide_next_action(
        questions_asked_in_level=4,
        correct_count_in_level=4,
        consecutive_wrong_count=0,
        total_levels=5,
        current_level_index=1,
        pass_threshold=4,
        questions_per_level=5,
        wrong_threshold_for_teaching=2,
    )
    assert out == NextAction.ADVANCE.value


def test_two_consecutive_wrong_triggers_teaching():
    out = decide_next_action(
        questions_asked_in_level=2,
        correct_count_in_level=0,
        consecutive_wrong_count=2,
        total_levels=5,
        current_level_index=1,
        pass_threshold=4,
        questions_per_level=5,
        wrong_threshold_for_teaching=2,
    )
    assert out == NextAction.TEACH.value


def test_failed_level_demotes_when_possible():
    out = decide_next_action(
        questions_asked_in_level=5,
        correct_count_in_level=2,
        consecutive_wrong_count=0,
        total_levels=5,
        current_level_index=2,
        pass_threshold=4,
        questions_per_level=5,
        wrong_threshold_for_teaching=2,
    )
    assert out == NextAction.DEMOTE.value


def test_final_level_pass_finishes_session():
    out = decide_next_action(
        questions_asked_in_level=4,
        correct_count_in_level=4,
        consecutive_wrong_count=0,
        total_levels=4,
        current_level_index=3,
        pass_threshold=4,
        questions_per_level=5,
        wrong_threshold_for_teaching=2,
    )
    assert out == NextAction.FINISH.value
