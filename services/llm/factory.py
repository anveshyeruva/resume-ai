from __future__ import annotations

from typing import Optional

from services.llm.local_ollama import OllamaProvider


def get_provider(
    ai_mode: str,
    *,
    ollama_base_url: str,
    ollama_model: str,
    cloud_provider: str,
    openai_api_key: str,
    openai_model: str,
) -> Optional[object]:
    """
    Factory for LLM providers.

    We pass runtime overrides (e.g., Streamlit session_state) so the app can
    toggle providers without mutating CONFIG (which is frozen).
    """
    mode = (ai_mode or "off").strip().lower()

    if mode == "off":
        return None

    if mode == "local":
        return OllamaProvider(
            base_url=ollama_base_url,
            model=ollama_model,
        )

    if mode == "cloud":
        provider = (cloud_provider or "").strip().lower()

        if provider == "openai":
            from services.llm.cloud_openai import OpenAIProvider

            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY is missing")
            return OpenAIProvider(
                api_key=openai_api_key,
                model=openai_model,
            )

        raise ValueError(f"Unsupported cloud provider: {provider}")

    raise ValueError(f"Unsupported ai_mode: {mode}")
