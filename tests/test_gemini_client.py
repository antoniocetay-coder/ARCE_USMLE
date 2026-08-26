from __future__ import annotations

import pytest

from ai.client import GeminiClientManager, GeminiConfigurationError
from ai.settings import AISettings


def test_client_manager_requires_a_key() -> None:
    with pytest.raises(GeminiConfigurationError):
        GeminiClientManager().get_client(AISettings(None, "gemini-2.5-flash", "gemini-2.5-flash"))


def test_client_manager_reuses_client_until_key_changes(monkeypatch) -> None:
    import google.genai

    created: list[str] = []

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            created.append(api_key)

    monkeypatch.setattr(google.genai, "Client", FakeClient)
    manager = GeminiClientManager()
    first = AISettings("first", "gemini-2.5-flash", "gemini-2.5-flash")
    second = AISettings("second", "gemini-2.5-flash", "gemini-2.5-flash")

    assert manager.get_client(first) is manager.get_client(first)
    manager.get_client(second)

    assert created == ["first", "second"]
