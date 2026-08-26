from __future__ import annotations

from types import SimpleNamespace

from ai.client import GeminiClientManager, generate_text


def test_generate_text_uses_models_generate_content_and_json_mime(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text='{"questions": []}')

    manager = GeminiClientManager(_api_key="key", _client=SimpleNamespace(models=FakeModels()))
    monkeypatch.setattr("ai.client._manager", manager)

    from ai.settings import AISettings
    settings = AISettings(api_key="key", question_model="gemini-2.5-flash", flashcard_model="gemini-2.5-flash")

    assert generate_text("prompt", "gemini-2.5-flash", settings=settings, response_json=True) == '{"questions": []}'
    assert calls[0]["model"] == "gemini-2.5-flash"
    assert calls[0]["contents"] == "prompt"
    assert calls[0]["config"].response_mime_type == "application/json"
