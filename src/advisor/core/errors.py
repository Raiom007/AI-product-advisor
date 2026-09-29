"""Custom exception hierarchy for the AI Product Advisor.

All advisor-specific errors inherit from AdvisorError so callers can
catch them with a single except clause while letting programming errors
(TypeError, ValueError) propagate normally.
"""
from __future__ import annotations


class AdvisorError(Exception):
    """Base class for all advisor application errors."""


class BudgetExceeded(AdvisorError):
    """Raised when the request budget (model calls or wall time) is exhausted.

    The agent catches this and degrades instead of crashing (§7, §5.9).
    """

    def __init__(self, reason: str, calls_used: int, limit: int) -> None:
        super().__init__(
            f"Budget exceeded — {reason}: used {calls_used}, limit {limit}"
        )
        self.reason = reason
        self.calls_used = calls_used
        self.limit = limit


class GatewayError(AdvisorError):
    """Raised when all LLM provider candidates are unavailable or rate-limited."""


class GroundingError(AdvisorError):
    """Raised when a generated statement fails the grounding validator (§5.7)."""


class ConfigError(AdvisorError):
    """Raised for missing or structurally invalid configuration."""


class RegistryError(AdvisorError):
    """Raised for duplicate registration or lookup of an unknown name."""
