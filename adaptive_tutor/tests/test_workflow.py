from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from adaptive_tutor.models.schemas import CurriculumPlan, EvaluationPayload, QuestionPayload, TeachingPayload
from adaptive_tutor.workflow import nodes
from adaptive_tutor.workflow.graph import build_graph


def _mock_curriculum():
    return CurriculumPlan(
        topic="math",
        topic_summary="summary",
        assumed_user_level="beginner",
        levels=[
            {"level_index": i, "title": f"L{i}", "goal": "g", "prerequisites": [], "success_criteria": "s", "remediation_focus": []}
            for i in range(4)
        ],
    )


def _mock_question(level_index: int = 0):
    return QuestionPayload(
        question_id="q1",
        level_index=level_index,
        concept_title="concept",
        question_type="SHORT_ANSWER",
        question_text="What is 2+2?",
        expected_key_points=["4"],
        hint="",
        difficulty_note="",
    )


def test_graph_builds_successfully():
    graph = build_graph()
    app = graph.compile(checkpointer=InMemorySaver())
    assert app is not None


def test_graph_interrupts_on_question(monkeypatch):
    monkeypatch.setattr(nodes, "create_curriculum", lambda _: _mock_curriculum())
    monkeypatch.setattr(nodes, "generate_question", lambda **_: _mock_question())

    app = build_graph().compile(checkpointer=InMemorySaver())
    result = app.invoke(
        {
            "session_id": "s1",
            "topic": "math",
            "curriculum": None,
            "current_level_index": 0,
            "current_question": None,
            "last_user_answer": None,
            "last_evaluation": None,
            "current_teaching": None,
            "questions_asked_in_level": 0,
            "correct_count_in_level": 0,
            "incorrect_count_in_level": 0,
            "consecutive_wrong_count": 0,
            "misconception_history": [],
            "next_action": None,
            "session_complete": False,
        },
        config={"configurable": {"thread_id": "s1"}},
    )
    assert "__interrupt__" in result


def test_graph_resumes_with_answer(monkeypatch):
    monkeypatch.setattr(nodes, "create_curriculum", lambda _: _mock_curriculum())
    monkeypatch.setattr(nodes, "generate_question", lambda **_: _mock_question())
    monkeypatch.setattr(
        nodes,
        "evaluate_answer",
        lambda **_: EvaluationPayload(
            question_id="q1",
            is_correct=True,
            score=1.0,
            matched_key_points=["4"],
            missing_key_points=[],
            misconception_tag=None,
            feedback="good",
            suggested_next_action="ADVANCE",
        ),
    )

    app = build_graph().compile(checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "s2"}}
    app.invoke(
        {
            "session_id": "s2",
            "topic": "math",
            "curriculum": None,
            "current_level_index": 0,
            "current_question": None,
            "last_user_answer": None,
            "last_evaluation": None,
            "current_teaching": None,
            "questions_asked_in_level": 0,
            "correct_count_in_level": 0,
            "incorrect_count_in_level": 0,
            "consecutive_wrong_count": 0,
            "misconception_history": [],
            "next_action": None,
            "session_complete": False,
        },
        config=cfg,
    )
    out = app.invoke(Command(resume={"answer": "4"}), config=cfg)
    assert "__interrupt__" in out


def test_teaching_path_works(monkeypatch):
    monkeypatch.setattr(nodes, "create_curriculum", lambda _: _mock_curriculum())
    monkeypatch.setattr(nodes, "generate_question", lambda **_: _mock_question())
    monkeypatch.setattr(
        nodes,
        "evaluate_answer",
        lambda **_: EvaluationPayload(
            question_id="q1",
            is_correct=False,
            score=0.1,
            matched_key_points=[],
            missing_key_points=["4"],
            misconception_tag="arith",
            feedback="wrong",
            suggested_next_action="TEACH",
        ),
    )
    monkeypatch.setattr(
        nodes,
        "generate_teaching",
        lambda **_: TeachingPayload(
            concept_title="arith",
            summary="2+2=4",
            why_user_was_wrong="mist",
            worked_example="2+2",
            memory_tip="pair pairs",
            checkpoint_question="3+1?",
        ),
    )

    app = build_graph().compile(checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "s3"}}
    app.invoke(
        {
            "session_id": "s3",
            "topic": "math",
            "curriculum": None,
            "current_level_index": 0,
            "current_question": None,
            "last_user_answer": None,
            "last_evaluation": None,
            "current_teaching": None,
            "questions_asked_in_level": 0,
            "correct_count_in_level": 0,
            "incorrect_count_in_level": 0,
            "consecutive_wrong_count": 1,
            "misconception_history": [],
            "next_action": None,
            "session_complete": False,
        },
        config=cfg,
    )
    out = app.invoke(Command(resume={"answer": "5"}), config=cfg)
    assert "__interrupt__" in out


def test_finish_path_works(monkeypatch):
    monkeypatch.setattr(nodes, "create_curriculum", lambda _: _mock_curriculum())
    monkeypatch.setattr(nodes, "generate_question", lambda **_: _mock_question(level_index=3))
    monkeypatch.setattr(
        nodes,
        "evaluate_answer",
        lambda **_: EvaluationPayload(
            question_id="q1",
            is_correct=True,
            score=1.0,
            matched_key_points=["4"],
            missing_key_points=[],
            misconception_tag=None,
            feedback="ok",
            suggested_next_action="FINISH",
        ),
    )

    app = build_graph().compile(checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "s4"}}
    app.invoke(
        {
            "session_id": "s4",
            "topic": "math",
            "curriculum": _mock_curriculum(),
            "current_level_index": 3,
            "current_question": _mock_question(level_index=3),
            "last_user_answer": None,
            "last_evaluation": None,
            "current_teaching": None,
            "questions_asked_in_level": 3,
            "correct_count_in_level": 3,
            "incorrect_count_in_level": 0,
            "consecutive_wrong_count": 0,
            "misconception_history": [],
            "next_action": None,
            "session_complete": False,
        },
        config=cfg,
    )
    out = app.invoke(Command(resume={"answer": "4"}), config=cfg)
    state = app.get_state(cfg).values
    assert state.get("session_complete") is True
