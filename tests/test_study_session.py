from state.study_session import StudySession


def test_question_submission_is_recorded_once_and_resets_on_next_item() -> None:
    session = StudySession(queue=[{"type": "question", "item": {"id": 7}}])

    assert session.record_question_submission("B", "Dúvida entre 2", 42, False) is True
    assert session.record_question_submission("B", "Dúvida entre 2", 42, False) is False
    assert session.answer_submitted is True
    assert session.selected_answer == "B"
    assert session.time_taken == 42

    session.next_item()

    assert session.current_index == 1
    assert session.answer_submitted is False
    assert session.selected_answer is None
    assert session.time_started is None


def test_session_instances_do_not_share_mutable_state() -> None:
    first = StudySession()
    second = StudySession()

    first.queue.append({"type": "flashcard"})
    first.draft_flashcards.append({"front": "A", "back": "B"})

    assert second.queue == []
    assert second.draft_flashcards == []
