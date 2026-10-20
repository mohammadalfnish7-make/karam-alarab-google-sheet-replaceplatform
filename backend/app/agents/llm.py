"""Facade over the evolvable provider registry (see agents/providers/)."""

from app.agents.providers import get_provider
from app.config import settings


def provider() -> str:
    return (settings.llm_provider or "anthropic").strip().lower() or "anthropic"


def model_name() -> str:
    return get_provider().model_name()


def generate_content(
    *,
    prompt: str,
    file_bytes: bytes | None = None,
    mime: str | None = None,
    files: list[tuple[bytes, str]] | None = None,
    max_tokens: int,
    thinking_budget: int | None = None,
) -> dict:
    return get_provider().generate_content(
        prompt=prompt,
        file_bytes=file_bytes,
        mime=mime,
        files=files,
        max_tokens=max_tokens,
        thinking_budget=thinking_budget,
    )
