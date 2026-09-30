import abc
from typing import Any, TypeVar

from pydantic import BaseModel

from advisor.llm.capabilities import LLMCapabilities

T = TypeVar("T", bound=BaseModel)

class ProviderResponse(BaseModel):
    text: str
    tokens_in: int
    tokens_out: int
    raw_response: Any = None
    structured_data: BaseModel | None = None

class LLMProvider(abc.ABC):
    """Port for interacting with language models."""

    @abc.abstractmethod
    def capabilities(self, model: str) -> LLMCapabilities:
        """Return the capabilities of this provider's model."""
        pass

    @abc.abstractmethod
    def complete(
        self,
        model: str,
        system: str | None,
        prompt: str,
        images: list[str] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None
    ) -> ProviderResponse:
        """Complete a text prompt.
        
        Args:
            model: Provider-specific model ID (e.g. 'gemini-3.5-flash')
            system: Optional system instruction
            prompt: User prompt
            images: Optional list of base64 encoded image strings or URIs (if supported)
            temperature: Sampling temperature
            max_tokens: Max output tokens
        """
        pass

    @abc.abstractmethod
    def structured(
        self,
        model: str,
        system: str | None,
        prompt: str,
        schema: type[T],
        images: list[str] | None = None,
        temperature: float = 0.0
    ) -> ProviderResponse:
        """Complete a text prompt, guaranteeing output adheres to a Pydantic schema.
        
        If the provider supports JSON-schema mode natively, it should use it.
        Otherwise, it is expected to raise an error or gateway will handle the parsing.
        """
        pass
