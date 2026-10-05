
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

import os

from advisor.llm.base import LLMProvider, ProviderResponse, T
from advisor.llm.capabilities import LLMCapabilities


class GeminiProvider(LLMProvider):
    def __init__(self):
        if genai is None:
            self._client = None
        else:
            try:
                self._client = genai.Client(
                    api_key=os.environ.get("GEMINI_API_KEY"),
                    http_options={"timeout": 15.0}
                )
            except Exception:
                import traceback
                traceback.print_exc()
                self._client = None

    def capabilities(self, model: str) -> LLMCapabilities:
        # According to standard Gemini models
        return LLMCapabilities(
            structured_output=True,
            vision="flash" in model or "pro" in model,
            max_context_window=1000000 if "1.5" in model else 32000,
            supports_system_prompt=True
        )

    def _prepare_contents(self, prompt: str, images: list[str] | None) -> list:
        contents = [prompt]
        if images:
            # Assumes base64 or file URIs; in a real app, parse this properly.
            pass
        return contents

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
            raise RuntimeError("google-genai SDK not installed")

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system
        )

        contents = self._prepare_contents(prompt, images)
        response = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=config
        )

        usage = response.usage_metadata
        return ProviderResponse(
            text=response.text,
            tokens_in=usage.prompt_token_count if usage else 0,
            tokens_out=usage.candidates_token_count if usage else 0,
            raw_response=response
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
            raise RuntimeError("google-genai SDK not installed")

        schema_dict = schema.model_json_schema()

        def _strip_additional_properties(d):
            if isinstance(d, dict):
                if "additionalProperties" in d:
                    del d["additionalProperties"]
                for v in d.values():
                    _strip_additional_properties(v)
            elif isinstance(d, list):
                for item in d:
                    _strip_additional_properties(item)

        _strip_additional_properties(schema_dict)

        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema_dict
        )

        contents = self._prepare_contents(prompt, images)
        response = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=config
        )

        usage = response.usage_metadata
        parsed = schema.model_validate_json(response.text)

        return ProviderResponse(
            text=response.text,
            tokens_in=usage.prompt_token_count if usage else 0,
            tokens_out=usage.candidates_token_count if usage else 0,
            raw_response=response,
            structured_data=parsed
        )
