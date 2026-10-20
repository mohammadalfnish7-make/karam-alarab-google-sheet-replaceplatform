from typing import Protocol


class DocumentProvider(Protocol):
    """Vision / document extract provider. Add new ones under providers/ and register them."""

    name: str

    def model_name(self) -> str: ...

    def generate_content(
        self,
        *,
        prompt: str,
        file_bytes: bytes | None = None,
        mime: str | None = None,
        files: list[tuple[bytes, str]] | None = None,
        max_tokens: int,
        thinking_budget: int | None = None,
    ) -> dict: ...
