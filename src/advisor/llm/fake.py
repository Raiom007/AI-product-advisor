import time

from advisor.llm.base import LLMProvider, ProviderResponse, T
from advisor.llm.capabilities import LLMCapabilities


class FakeLLMProvider(LLMProvider):
    """Deterministic test double for LLMProvider.
    
    Can simulate 429, 5xx, timeouts, malformed JSON and vision input via 
    pre-configured behaviors or special prompt keywords.
    """

    def __init__(self):
        self._capabilities = LLMCapabilities(
            structured_output=True,
            vision=True,
            max_context_window=8192,
            supports_system_prompt=True
        )
        self.trigger_429 = False
        self.trigger_5xx = False
        self.trigger_timeout = False
        self.trigger_malformed = False
        self.call_count = 0

    def capabilities(self, model: str) -> LLMCapabilities:
        vision_support = "text-only" not in model.lower()
        return LLMCapabilities(
            structured_output=True,
            vision=vision_support,
            max_context_window=8192,
            supports_system_prompt=True
        )

    def _check_triggers(self, prompt: str):
        self.call_count += 1
        if self.trigger_429 or "TRIGGER_429" in prompt:
            raise Exception("429 Too Many Requests")
        if self.trigger_5xx or "TRIGGER_5XX" in prompt:
            raise Exception("500 Internal Server Error")
        if self.trigger_timeout or "TRIGGER_TIMEOUT" in prompt:
            time.sleep(0.1) # Simulate just enough to show intent, then raise
            raise TimeoutError("Request timed out")

    def complete(
        self,
        model: str,
        system: str | None,
        prompt: str,
        images: list[str] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None
    ) -> ProviderResponse:
        self._check_triggers(prompt)

        vision_msg = f" [Vision: {len(images)} images]" if images else ""
        return ProviderResponse(
            text=f"Fake response to: {prompt[:20]}...{vision_msg}",
            tokens_in=len(prompt) // 4,
            tokens_out=10
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
        self._check_triggers(prompt)

        if self.trigger_malformed or "TRIGGER_MALFORMED" in prompt:
            # We must raise an exception so Gateway catches and retries
            # The prompt asks for ONE repair retry
            if "Fix it" in prompt:
                # This is the repair retry! It works now
                self.trigger_malformed = False
            else:
                raise ValueError("Malformed JSON")

        if images and "VisualCheck" in schema.__name__:
            try:
                dummy = schema(
                    claim="Test claim",
                    source_ref="test_ref",
                    verdict="agree",
                    observation=f"Fake observation from {len(images)} images",
                    image_ids=["img1"]
                )
            except:
                dummy = schema.model_construct()
        else:
            try:
                dummy = schema.model_construct()
            except:
                dummy = schema()

        return ProviderResponse(
            text=dummy.model_dump_json(),
            tokens_in=len(prompt) // 4,
            tokens_out=50,
            structured_data=dummy
        )
