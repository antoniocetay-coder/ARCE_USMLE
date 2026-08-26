from state.study_session import StudySession


def card(card_id: int = 1) -> dict:
    return {"type": "flashcard", "item": {"id": card_id, "front": "F", "back": "B"}}


def test_end_session_before_first_item_clears_all_transient_state() -> None:
    session = StudySession(mode="Review", queue=[card()])
    session.selected_answer = "A"
    session.draft_flashcards = [{"front": "draft"}]
    session.end()
    assert session.mode is None
    assert session.queue == []
    assert session.selected_answer is None
    assert session.draft_flashcards == []


def test_flashcard_again_requeues_same_entity_with_bounded_attempts() -> None:
    item = card()
    session = StudySession(mode="Review", queue=[item])
    assert session.requeue_item(item, "Again")
    assert session.queue[-1] is item
    assert item["same_session_attempts"] == 1
    item["same_session_attempts"] = 3
    assert not session.requeue_item(item, "Again")


def test_hard_requeues_once_and_good_easy_do_not_requeue() -> None:
    item = card()
    session = StudySession(mode="Review", queue=[item])
    assert session.requeue_item(item, "Hard")
    assert not session.requeue_item(item, "Hard")
    assert not session.requeue_item(item, "Good")
    assert not session.requeue_item(item, "Easy")


def test_generated_flashcard_is_unique_at_end_of_current_session() -> None:
    session = StudySession(mode="QBank", queue=[{"type": "question", "item": {"id": 9}}])
    generated = card(7)
    assert session.append_item(generated)
    assert session.queue[-1]["item"]["id"] == 7
    assert not session.append_item(card(7))
