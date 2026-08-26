from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai.settings import AISettings, load_ai_settings
from core.exceptions import StudyApplicationError


class GeminiServiceError(StudyApplicationError):
    """A Gemini failure that is safe to expose to the local user."""


class GeminiConfigurationError(GeminiServiceError):
    pass


@dataclass
class GeminiClientManager:
    _api_key: str | None = None
    _client: Any = None

    def get_client(self, settings: AISettings) -> Any:
        if not settings.api_key:
            raise GeminiConfigurationError("Configure uma chave válida da API Gemini (começando com AIzaSy...) nas Configurações.")
        if self._client is not None and self._api_key == settings.api_key:
            return self._client
        from google import genai
        from google.genai import types
        self._api_key = settings.api_key
        try:
            http_options = types.HttpOptions(client_args={"trust_env": False})
            self._client = genai.Client(api_key=settings.api_key, http_options=http_options)
        except TypeError:
            self._client = genai.Client(api_key=settings.api_key)
        return self._client

    def invalidate(self) -> None:
        self._api_key = None
        self._client = None


_manager = GeminiClientManager()


def invalidate_client() -> None:
    _manager.invalidate()


def _friendly_error(error: Exception) -> GeminiServiceError:
    detail = str(error).lower()
    if any(code in detail for code in ("401", "403", "api key", "permission_denied", "unauthenticated", "invalid_argument", "bad request")):
        return GeminiServiceError("A chave Gemini configurada é inválida ou não autorizada. Verifique sua chave no Google AI Studio (começa com AIzaSy...).")
    if any(code in detail for code in ("404", "not found", "model not")):
        return GeminiServiceError("O modelo Gemini selecionado não existe ou não está disponível para esta chave. Altere o modelo nas Configurações.")
    if any(code in detail for code in ("429", "resource_exhausted", "quota", "rate limit")):
        return GeminiServiceError("O limite de uso da API Gemini foi atingido. Tente novamente mais tarde.")
    if any(word in detail for word in ("blocked", "safety", "blocked_prompt")):
        return GeminiServiceError("A resposta foi bloqueada pelos filtros de segurança do Gemini.")
    if any(word in detail for word in ("connection", "timeout", "network", "dns")):
        return GeminiServiceError("Não foi possível conectar à API Gemini. Verifique sua conexão de rede.")
    return GeminiServiceError(f"Falha na comunicação com a API Gemini: {error}")


def generate_text(prompt: str, model: str, *, settings: AISettings | None = None, response_json: bool = False, use_cache: bool = False) -> str:
    import logging
    import random
    import time

    from google.genai import types

    from core.ai.ai_cache import get_cached_response, store_cached_response

    logger = logging.getLogger(__name__)
    active = settings or load_ai_settings()

    if use_cache:
        cached = get_cached_response(prompt, model)
        if cached:
            logger.info("Retornando resposta do cache para prompt_hash (%s)", model)
            return cached

    config = types.GenerateContentConfig(response_mime_type="application/json") if response_json else None

    max_retries_per_model = 3
    base_delay_seconds = 1.0

    candidates = [model, "gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.5-flash"]
    seen = set()
    fallback_queue = [m for m in candidates if m and not (m in seen or seen.add(m))]

    last_error: Exception | None = None

    for target_model in fallback_queue:
        for attempt in range(1, max_retries_per_model + 1):
            try:
                client = _manager.get_client(active)
                response = client.models.generate_content(model=target_model, contents=prompt, config=config)
                text = getattr(response, "text", None)
                if not isinstance(text, str) or not text.strip():
                    raise GeminiServiceError("O Gemini retornou uma resposta vazia.")
                if use_cache:
                    store_cached_response(prompt, model, text)
                return text
            except Exception as error:
                detail = str(error).lower()
                logger.warning("Gemini model %s attempt %d/%d failed: %s", target_model, attempt, max_retries_per_model, error)
                last_error = error
                if any(term in detail for term in ("404", "not found", "no longer available")):
                    # Model not found / deprecated -> skip directly to next model
                    break
                if any(term in detail for term in ("503", "429", "unavailable", "high demand", "quota", "resource_exhausted")):
                    sleep_time = (base_delay_seconds * (2 ** (attempt - 1))) + random.uniform(0.1, 0.6)
                    time.sleep(sleep_time)
                    continue
                if any(code in detail for code in ("401", "403", "api key", "permission_denied", "unauthenticated", "invalid_argument")):
                    raise _friendly_error(error) from error
                break

    if last_error:
        raise _friendly_error(last_error) from last_error
    raise GeminiServiceError("Não foi possível conectar aos modelos da API Gemini.")



def test_connection(api_key: str, model: str) -> None:
    if not api_key or not api_key.strip():
        raise GeminiConfigurationError("A chave da API Gemini não foi fornecida.")
    candidate = AISettings(api_key=api_key.strip(), question_model=model, flashcard_model=model)
    try:
        client = GeminiClientManager().get_client(candidate)
        response = client.models.generate_content(model=model, contents="Reply with OK.")
        if not getattr(response, "text", "").strip():
            raise GeminiServiceError("O Gemini retornou uma resposta vazia.")
    except GeminiServiceError:
        raise
    except Exception as error:
        raise _friendly_error(error) from error

