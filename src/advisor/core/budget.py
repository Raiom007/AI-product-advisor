"""Request budget: tracks model calls and wall-clock time per advise() request.

Per §5.9:
  - max_model_calls (default 12): total model calls across all roles.
  - max_wall_s (default 18): wall-clock seconds for the entire request.
  - per_role_caps: e.g. vision ≤ 3, parser ≤ 1.

The budget object travels in AgentState. When charge() raises BudgetExceeded,
the agent degrades instead of crashing (§7 degradation ladder).

WHY: Hard limit on model calls is the primary defence against runaway quota
     usage on the free tier (AGENTS.md "LLM quota discipline").
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from advisor.core.errors import BudgetExceeded


@dataclass
class RequestBudget:
    """Mutable budget state for one advise() request.

    All limits are sourced from configs/limits.yaml — never hard-coded here.
    """
    max_model_calls: int = 12
    max_wall_s: float = 18.0
    per_role_caps: dict[str, int] = field(default_factory=dict)

    # Internal state — not part of the constructor signature
    _calls_used: int = field(default=0, init=False, repr=False)
    _role_calls: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _start_time: float = field(default_factory=time.monotonic, init=False, repr=False)

    @classmethod
    def from_config(cls, limits: dict) -> "RequestBudget":
        """Build a RequestBudget from the 'limits' section of load_config()."""
        rb = limits.get("request_budget", {})
        return cls(
            max_model_calls=rb.get("max_model_calls", 12),
            max_wall_s=rb.get("max_wall_s", 18.0),
            per_role_caps=rb.get("per_role_caps", {}),
        )

    def charge(self, role: str, calls: int = 1) -> None:
        """Record that `calls` model calls were used for `role`.

        Raises BudgetExceeded if any limit would be exceeded.
        Check order: wall time first (cheapest), then total calls, then role cap.
        """
        elapsed = time.monotonic() - self._start_time
        if elapsed >= self.max_wall_s:
            raise BudgetExceeded(
                reason="wall_time",
                calls_used=self._calls_used,
                limit=int(self.max_wall_s),
            )

        projected = self._calls_used + calls
        if projected > self.max_model_calls:
            raise BudgetExceeded(
                reason="model_calls",
                calls_used=self._calls_used,
                limit=self.max_model_calls,
            )

        cap = self.per_role_caps.get(role)
        if cap is not None:
            role_used = self._role_calls.get(role, 0)
            if role_used + calls > cap:
                raise BudgetExceeded(
                    reason=f"role_cap:{role}",
                    calls_used=role_used,
                    limit=cap,
                )
            self._role_calls[role] = role_used + calls

        self._calls_used += calls

    def report(self) -> dict:
        """Return a serialisable snapshot for AdvisorResponse.budget_report."""
        return {
            "calls_used": self._calls_used,
            "calls_limit": self.max_model_calls,
            "wall_s": round(time.monotonic() - self._start_time, 3),
            "wall_limit_s": self.max_wall_s,
            "per_role": dict(self._role_calls),
        }
