"""Provider registry — add new image/document backends here over time."""

from __future__ import annotations

from app.agents.providers.base import DocumentProvider
from app.config import settings
from app.errors import AppError

_PROVIDERS: dict[str, DocumentProvider] = {}


def register(provider: DocumentProvider) -> DocumentProvider:
    name = provider.name.strip().lower()
    if not name:
        raise ValueError("Provider name is required")
    _PROVIDERS[name] = provider
    return provider


def known_providers() -> list[str]:
    return sorted(_PROVIDERS)


def get_provider(name: str | None = None) -> DocumentProvider:
    key = (name or settings.llm_provider or "").strip().lower() or "anthropic"
    provider = _PROVIDERS.get(key)
    if provider is None:
        available = ", ".join(known_providers()) or "(none registered)"
        raise AppError(
            503,
            {
                "message": f"Unknown LLM_PROVIDER {key!r}. Registered: {available}.",
                "field_errors": {},
                "warnings": [],
            },
        )
    return provider


def load_builtin_providers() -> None:
    """Import built-in providers so they register themselves."""
    from app.agents.providers import anthropic as _anthropic  # noqa: F401
