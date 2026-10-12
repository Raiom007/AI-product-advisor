
try:
    from groq import Groq
except ImportError:
    Groq = None

import os

from advisor.llm.base import LLMProvider, ProviderResponse, T
from advisor.llm.capabilities import LLMCapabilities


class GroqProvider(LLMProvider):
    def __init__(self):
        self._init_error = None
        if Groq is None:
            self._client = None
            self._init_error = "groq SDK not installed"
        else:
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                self._client = None
                self._init_error = "GROQ_API_KEY environment variable not set"
            else:
                try:
                    self._client = Groq(api_key=api_key, timeout=15.0)
                except Exception as e:
                    self._client = None
                    self._init_error = f"Failed to initialize Groq Client: {e}"

    def capabilities(self, model: str) -> LLMCapabilities:
        # Vision is supported on Llama 3.2 vision models
        vision = "vision" in model.lower()
        return LLMCapabilities(
            structured_output=True, # Groq supports JSON mode
            vision=vision,
            max_context_window=8192,
            supports_system_prompt=True
        )

    def _build_messages(self, system: str | None, prompt: str) -> list[dict]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def complete(
        self,
        model: str,
        system: str | None,
        prompt: str,
        images: list[str] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None
    ) -> ProviderResponse:
        if not self._client:
            raise RuntimeError(self._init_error or "groq Client not initialized")

        messages = self._build_messages(system, prompt)

        completion = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens or 1024
        )

        usage = completion.usage
        return ProviderResponse(
            text=completion.choices[0].message.content,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            raw_response=completion
        )

    def structured(
        self,
        model: str,
        system: str | None,
        prompt: str,
        schema: type[T],
        images: list[str] | None = None,
        temperature: float = 0.0
    ) -> ProviderResponse:
        if not self._client:
            raise RuntimeError(self._init_error or "groq Client not initialized")

        # Add a hint to the prompt for JSON mode
        system = (system or "") + "\n\nYou must output ONLY valid JSON adhering to the provided schema."
        messages = self._build_messages(system, prompt)

        # In a real app we'd pass response_format={"type": "json_object"}
        # But for strictly adhering to schema, we rely on the prompt instructing it.
        # Groq supports JSON mode.
        completion = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"}
        )

        text = completion.choices[0].message.content
        usage = completion.usage

        try:
            parsed = schema.model_validate_json(text)
        except Exception as e:
            # In a robust implementation, we might raise a custom parsing error to retry
            raise ValueError(f"Failed to parse Groq response: {e}\n{text}")

        return ProviderResponse(
            text=text,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            raw_response=completion,
            structured_data=parsed
        )
