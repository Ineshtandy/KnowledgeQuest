from fastapi.testclient import TestClient

from adaptive_tutor.api.main import app


def test_session_creation_endpoint_works(monkeypatch):
    monkeypatch.setattr(
        "adaptive_tutor.api.routes.start_session",
        lambda topic: {
            "session_id": "s1",
            "topic": topic,
            "question": {"question_text": "What is supervised learning?", "question_id": "q1"},
            "session_complete": False,
        },
    )

    client = TestClient(app)
    response = client.post("/sessions", json={"topic": "machine learning"})
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "s1"
    assert "question" in data


def test_answer_submission_endpoint_works(monkeypatch):
    monkeypatch.setattr(
        "adaptive_tutor.api.routes.submit_answer",
        lambda session_id, answer: {
            "session_id": session_id,
            "evaluation": {"feedback": "Good", "score": 0.9},
            "teaching": None,
            "next_question": {"question_text": "Next?", "question_id": "q2"},
            "session_complete": False,
            "next_action": "CONTINUE",
            "current_level_index": 0,
        },
    )

    client = TestClient(app)
    response = client.post("/sessions/s1/answer", json={"answer": "with labels"})
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "s1"
    assert data["evaluation"]["feedback"] == "Good"
    assert data["next_question"]["question_id"] == "q2"
