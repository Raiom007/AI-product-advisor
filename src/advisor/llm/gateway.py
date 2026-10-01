import hashlib
import json
import logging
import random
import time

from pydantic import BaseModel

from advisor.core.budget import RequestBudget
from advisor.core.tracing import Tracer
from advisor.llm.base import LLMProvider, ProviderResponse, T
from advisor.llm.fake import FakeLLMProvider
from advisor.llm.gemini import GeminiProvider
from advisor.llm.groq import GroqProvider
from advisor.llm.ratelimit import RateLimiter

logger = logging.getLogger(__name__)

class GatewayError(Exception): pass
class BudgetExceeded(GatewayError): pass

class Gateway:
    def __init__(self, models_config: dict, limits_config: dict, cache_dir: str = "data/cache"):
        self.models_config = models_config
        self.rate_limiter = RateLimiter(limits_config)
        self.providers: dict[str, LLMProvider] = {
            "gemini": GeminiProvider(),
            "groq": GroqProvider(),
            "fake": FakeLLMProvider()
        }
        self.cache_dir = cache_dir
        self.resolved_roles = {}

    def self_check(self) -> None:
        """Resolve each role to the first candidate that exists and has required capabilities."""
        available_models = {}
        # Try to list models to see what's actually alive (mocked for simplicity, in reality we'd call SDK list methods)
        # For this MVP, we assume all providers are available unless they fail initialization

        for role, config in self.models_config.get("roles", {}).items():
            resolved = None
            for cand in config.get("candidates", []):
                provider_name = cand["provider"]
                model_id = cand["model"]
                needs = cand.get("needs", [])

                provider = self.providers.get(provider_name)
                if not provider:
                    continue

                # Cross-reference with configs/limits.yaml (the probe output)
                if provider_name != "fake" and model_id not in self.rate_limiter.buckets:
                    logger.debug(f"Skipping {model_id}: not present in probed limits config.")
                    continue

                caps = provider.capabilities(model_id)

                # Check needs
                missing = False
                for need in needs:
                    if need == "structured_output" and not caps.structured_output: missing = True
                    if need == "vision" and not caps.vision: missing = True

                if not missing:
                    resolved = cand
                    break

            if resolved:
                self.resolved_roles[role] = resolved
                logger.info(f"Role '{role}' resolved to {resolved['provider']}/{resolved['model']}")
            else:
                logger.error(f"Role '{role}' has no live candidate satisfying needs!")
                # Fail loudly per SOW
                raise RuntimeError(f"Startup check failed: no candidate for role '{role}'")

    def _get_cache_key(self, model: str, role: str, prompt: str, schema: type[BaseModel] | None, params: dict) -> str:
        data = {
            "model": model,
            "role": role,
            "prompt": prompt,
            "schema": schema.model_json_schema() if schema else None,
            "params": params
        }
        h = hashlib.sha256()
        h.update(json.dumps(data, sort_keys=True).encode())
        return h.hexdigest()

    def _invoke_with_retry(self, provider: LLMProvider, model: str, method: str, kwargs: dict) -> ProviderResponse:
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                func = getattr(provider, method)
                return func(**kwargs)
            except Exception as e:
                err_str = str(e).lower()
                is_retryable = "429" in err_str or "500" in err_str or "502" in err_str or "503" in err_str or isinstance(e, TimeoutError)

                if not is_retryable or attempt == max_retries - 1:
                    raise e

                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(f"Retryable error on {model}: {e}. Retrying in {delay:.2f}s...")
                time.sleep(delay)

        raise RuntimeError("Unreachable")

    def _read_cache(self, key: str) -> ProviderResponse | None:
        if not hasattr(self, "_cache"):
            self._cache = {}
        return self._cache.get(key)

    def _write_cache(self, key: str, resp: ProviderResponse) -> None:
        if not hasattr(self, "_cache"):
            self._cache = {}
        self._cache[key] = resp

    def call(self, role: str, prompt: str, system: str | None = None, schema: type[T] | None = None, images: list[str] | None = None, budget: RequestBudget | None = None, tracer: Tracer | None = None) -> ProviderResponse:
        candidates = self.models_config["roles"][role]["candidates"]
        last_err = None

        for cand in candidates:
            provider_name = cand["provider"]
            model = cand["model"]
            params = cand.get("params", {})
            provider = self.providers.get(provider_name)

            if not provider:
                continue

            cache_key = self._get_cache_key(model, role, prompt, schema, params)

            cached = self._read_cache(cache_key)
            if cached:
                logger.info(f"Cache hit for {model}/{role}")
                if tracer: tracer.span("model_call", model=model, cache_hit=True)
                return cached

            if budget:
                # We charge before calling so that if it fails due to limits, we don't call.
                # However, if we fallback, charging again might be double charging?
                # We will charge just before the call to the provider.
                budget.charge(role, calls=1)

            try:
                est = len(prompt) // 4
                self.rate_limiter.wait_if_needed(model, estimated_tokens=est)
            except Exception as e:
                logger.warning(f"Rate limiter rejected {model}: {e}")
                last_err = e
                continue

            try:
                kwargs = {
                    "model": model,
                    "system": system,
                    "prompt": prompt,
                    "images": images,
                    "temperature": params.get("temperature", 0.0),
                }

                resp = None
                if schema:
                    kwargs["schema"] = schema
                    try:
                        resp = self._invoke_with_retry(provider, model, "structured", kwargs)
                    except Exception as e:
                        if "parse" in str(e).lower() or "validation" in str(e).lower() or "malformed json" in str(e).lower():
                            logger.warning(f"Malformed JSON from {model}. Attempting 1 repair retry...")
                            repair_kwargs = kwargs.copy()
                            repair_kwargs["prompt"] = prompt + f"\n\nYou failed to provide valid JSON matching the schema. Error: {e}. Fix it."
                            if budget: budget.charge(role, calls=1) # charge for retry
                            resp = self._invoke_with_retry(provider, model, "structured", repair_kwargs)
                        else:
                            raise e
                else:
                    kwargs["max_tokens"] = params.get("max_output_tokens") or params.get("max_tokens")
                    resp = self._invoke_with_retry(provider, model, "complete", kwargs)

                self.rate_limiter.record_usage(model, resp.tokens_in + resp.tokens_out)

                if tracer:
                    tracer.span("model_call", model=model, tokens_in=resp.tokens_in, tokens_out=resp.tokens_out, cache_hit=False)

                self._write_cache(cache_key, resp)
                return resp

            except Exception as e:
                logger.warning(f"Provider {provider_name}/{model} failed for role {role}: {e}")
                last_err = e
                # Fallback to next candidate

        raise GatewayError(f"All candidates failed for role {role}. Last error: {last_err}")
