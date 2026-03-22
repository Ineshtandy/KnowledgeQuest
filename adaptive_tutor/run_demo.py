from adaptive_tutor.engine.runner import start_session, submit_answer


def main() -> None:
    topic = input("Enter topic: ").strip()
    if not topic:
        print("Topic is required")
        return

    session = start_session(topic)
    session_id = session["session_id"]
    question = session.get("question")

    while True:
        if session.get("session_complete"):
            print("Session completed.")
            break

        if not question:
            print("No question available. Exiting.")
            break

        print(f"\nQuestion: {question['question_text']}")
        answer = input("> ").strip()
        result = submit_answer(session_id=session_id, answer=answer)

        evaluation = result.get("evaluation")
        if evaluation:
            print(f"Feedback: {evaluation['feedback']}")
            print(f"Score: {evaluation['score']}")

        teaching = result.get("teaching")
        if teaching:
            print("Teaching:")
            print(f"- Summary: {teaching['summary']}")
            print(f"- Why wrong: {teaching['why_user_was_wrong']}")
            print(f"- Worked example: {teaching['worked_example']}")
            print(f"- Memory tip: {teaching['memory_tip']}")
            print(f"- Checkpoint: {teaching['checkpoint_question']}")

        if result.get("session_complete"):
            print("Session completed.")
            break

        question = result.get("next_question")
        if question:
            print(f"Next question: {question['question_text']}")


if __name__ == "__main__":
    main()
