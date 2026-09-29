"""Tests for core/budget.py."""
from __future__ import annotations

import pytest

from advisor.core.budget import RequestBudget
from advisor.core.errors import BudgetExceeded


def test_charge_increments_calls():
    budget = RequestBudget(max_model_calls=5)
    budget.charge("parser")
    assert budget.report()["calls_used"] == 1


def test_charge_multiple_calls_at_once():
    budget = RequestBudget(max_model_calls=10)
    budget.charge("summarizer", calls=3)
    assert budget.report()["calls_used"] == 3


def test_exceeds_total_cap_raises():
    budget = RequestBudget(max_model_calls=2)
    budget.charge("parser")
    budget.charge("summarizer")
    with pytest.raises(BudgetExceeded) as exc_info:
        budget.charge("composer")
    assert exc_info.value.reason == "model_calls"
    assert exc_info.value.calls_used == 2
    assert exc_info.value.limit == 2


def test_per_role_cap_raises():
    budget = RequestBudget(max_model_calls=10, per_role_caps={"vision": 3})
    budget.charge("vision")
    budget.charge("vision")
    budget.charge("vision")
    with pytest.raises(BudgetExceeded) as exc_info:
        budget.charge("vision")
    assert "vision" in exc_info.value.reason
    assert exc_info.value.calls_used == 3
    assert exc_info.value.limit == 3


def test_per_role_cap_does_not_block_other_roles():
    budget = RequestBudget(max_model_calls=10, per_role_caps={"vision": 1})
    budget.charge("vision")  # exhausted
    # Other roles still work
    budget.charge("parser")
    assert budget.report()["calls_used"] == 2


def test_report_structure_complete():
    budget = RequestBudget(max_model_calls=12, max_wall_s=18.0)
    budget.charge("parser")
    report = budget.report()
    assert set(report.keys()) >= {"calls_used", "calls_limit", "wall_s", "wall_limit_s", "per_role"}
    assert report["calls_limit"] == 12
    assert report["wall_limit_s"] == 18.0
    assert isinstance(report["wall_s"], float)


def test_from_config():
    limits = {
        "request_budget": {
            "max_model_calls": 8,
            "max_wall_s": 15.0,
            "per_role_caps": {"vision": 2, "parser": 1},
        }
    }
    budget = RequestBudget.from_config(limits)
    assert budget.max_model_calls == 8
    assert budget.max_wall_s == 15.0
    assert budget.per_role_caps == {"vision": 2, "parser": 1}


def test_from_config_defaults_when_section_missing():
    budget = RequestBudget.from_config({})
    assert budget.max_model_calls == 12
    assert budget.max_wall_s == 18.0


def test_budget_exceeded_str():
    exc = BudgetExceeded(reason="model_calls", calls_used=12, limit=12)
    assert "model_calls" in str(exc)
    assert "12" in str(exc)
