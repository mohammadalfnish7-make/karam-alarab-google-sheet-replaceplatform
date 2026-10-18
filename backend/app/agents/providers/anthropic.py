import base64

import httpx

from app.agents.providers.registry import register
from app.config import settings
from app.errors import AppError

_API = "https://api.anthropic.com/v1/messages"
_VERSION = "2023-06-01"
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MISSING_KEY = "ANTHROPIC_API_KEY is not configured. The file is stored; extraction was not run."


class AnthropicProvider:
    name = "anthropic"

    def model_name(self) -> str:
        return (settings.llm_model or "").strip() or "claude-haiku-5-5"

    def generate_content(
        self,
        *,
        prompt: str,
        file_bytes: bytes,
        mime: str,
        max_tokens: int,
        thinking_budget: int | None = None,
    ) -> dict:
        del thinking_budget  # Anthropic adaptive thinking is model-default; not used here.
        key = settings.anthropic_api_key.strip()
        if not key:
            raise AppError(503, {"message": _MISSING_KEY, "field_errors": {}, "warnings": []})
        payload = {
            "model": self.model_name(),
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        _file_block(file_bytes, mime),
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        try:
            response = httpx.post(
                _API,
                headers={
                    "x-api-key": key,
                    "anthropic-version": _VERSION,
                    "content-type": "application/json",
                },
                json=payload,
                timeout=settings.llm_timeout_sec,
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise AppError(
                502,
                {
                    "message": f"Anthropic request failed: {exc.response.status_code} {detail}",
                    "field_errors": {},
                    "warnings": [],
                },
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                502,
                {"message": f"Anthropic request failed: {exc}", "field_errors": {}, "warnings": []},
            ) from exc
        return {
            "text": _reply_text(body),
            "finish": str(body.get("stop_reason") or ""),
            "usage": _usage(body),
            "provider": self.name,
            "model": self.model_name(),
            "body": body,
        }


def _file_block(file_bytes: bytes, mime: str) -> dict:
    media = (mime or "").split(";")[0].strip().lower() or "application/octet-stream"
    data = base64.b64encode(file_bytes).decode("ascii")
    if media == "application/pdf":
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": data},
        }
    if media not in _IMAGE_TYPES:
        raise AppError(
            422,
            {
                "message": f"Anthropic provider accepts PDF or image (jpeg/png/gif/webp), not {media!r}.",
                "field_errors": {},
                "warnings": [],
            },
        )
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media, "data": data},
    }


def _reply_text(body: dict) -> str:
    parts = body.get("content") or []
    texts = [
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("type") == "text"
    ]
    return "\n".join(text for text in texts if text)


def _usage(body: dict) -> dict | None:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return None
    return {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
    }


register(AnthropicProvider())
