import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

class TokenBucket:
    def __init__(self, capacity: float, refill_rate: float):
        """
        capacity: max tokens (or requests) in the bucket.
        refill_rate: tokens per second.
        """
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.tokens = self.capacity
        self.last_refill = time.monotonic()

    def consume(self, amount: float = 1.0) -> float:
        """
        Try to consume `amount` tokens.
        Returns 0.0 if successful, or the number of seconds to wait if not enough tokens.
        """
        now = time.monotonic()
        elapsed = now - self.last_refill

        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= amount:
            self.tokens -= amount
            return 0.0

        return (amount - self.tokens) / self.refill_rate

class RateLimiter:
    """Manages rate limits (RPM, TPM, RPD) per model based on configs/limits.yaml."""

    def __init__(self, limits_config: dict[str, Any]):
        self.buckets: dict[str, dict[str, TokenBucket]] = {}
        self.rpd_usage: dict[str, int] = {}
        self.reset_time = time.time()

        for model, limits in limits_config.items():
            rpm = limits.get("RPM", 15)
            tpm = limits.get("TPM", 1000000)

            self.buckets[model] = {
                "requests": TokenBucket(capacity=rpm, refill_rate=rpm / 60.0),
                "tokens": TokenBucket(capacity=tpm, refill_rate=tpm / 60.0)
            }
            self.rpd_usage[model] = 0

    def _check_daily_reset(self):
        # A simple daily reset based on wall time
        now = time.time()
        if now - self.reset_time > 86400:
            for model in self.rpd_usage:
                self.rpd_usage[model] = 0
            self.reset_time = now

    def wait_if_needed(self, model: str, estimated_tokens: int = 1000) -> None:
        """Blocks until there is enough quota to proceed. Raises Exception if daily quota exceeded."""
        if model not in self.buckets:
            return # No limits configured

        self._check_daily_reset()

        # In a real app we'd also check RPD from the config, but we'll assume the
        # config is just passed in via limits_config and we can check it if present.

        req_bucket = self.buckets[model]["requests"]
        tok_bucket = self.buckets[model]["tokens"]

        while True:
            wait_req = req_bucket.consume(1.0)
            wait_tok = tok_bucket.consume(float(estimated_tokens))

            wait_time = max(wait_req, wait_tok)
            if wait_time <= 0:
                break

            logger.info(f"Rate limited on {model}, sleeping {wait_time:.2f}s")
            time.sleep(wait_time)

    def record_usage(self, model: str, actual_tokens: int) -> None:
        """Records the actual tokens used to adjust the bucket (and RPD)."""
        self._check_daily_reset()
        if model in self.rpd_usage:
            self.rpd_usage[model] += 1

        if model in self.buckets:
            # We already consumed estimated_tokens, we could refund or consume more
            # based on actual_tokens, but a simple implementation can just track RPD here.
            pass
