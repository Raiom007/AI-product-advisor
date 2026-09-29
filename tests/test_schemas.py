"""Tests for core/schemas.py — validation, JSON round-trip, ext preserved,
RunManifest stamped on AdvisorResponse.
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from advisor.core.manifest import RunManifest
from advisor.core.schemas import (
    AdvisorResponse,
    Budget,
    Constraint,
    EvidenceRef,
    GuardResult,
    ParsedQuery,
    Recommendation,
    ReviewFlag,
    ReviewSummary,
    ScoreBreakdown,
    ToolCost,
    ToolResult,
    Verdict,
    VisualCheck,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score(**kwargs) -> ScoreBreakdown:
    defaults = dict(
        relevance=0.8, soft_fit=0.7, use_case_sentiment=0.6,
        review_trust=0.9, visual=0.5, total=0.74,
        weights_used={"relevance": 0.30, "soft_fit": 0.15,
                      "use_case_sentiment": 0.30, "review_trust": 0.15, "visual": 0.10},
    )
    defaults.update(kwargs)
    return ScoreBreakdown(**defaults)


def _recommendation(**kwargs) -> Recommendation:
    defaults = dict(
        product_id="P001", rank=1,
        paragraph="Great laptop for video editing.",
        statements=[{"text": "Good GPU.", "evidence_ids": ["spec:P001:3"]}],
        constraint_evidence={"budget": ["spec:P001:1"]},
        review_quotes=["rev:R10", "rev:R11"],
        image_observations=[],
        score=_score(),
        confidence="high",
    )
    defaults.update(kwargs)
    return Recommendation(**defaults)


def _response(**kwargs) -> AdvisorResponse:
    defaults = dict(
        status="ok",
        recommendations=[_recommendation()],
        trace_id="trace-001",
        budget_report={"calls_used": 8, "calls_limit": 12},
    )
    defaults.update(kwargs)
    return AdvisorResponse(**defaults)


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

def test_budget_defaults_none():
    b = Budget()
    assert b.min_inr is None
    assert b.max_inr is None


def test_budget_with_values():
    b = Budget(min_inr=10000.0, max_inr=40000.0)
    assert b.max_inr == 40000.0


# ---------------------------------------------------------------------------
# Constraint
# ---------------------------------------------------------------------------

def test_constraint_valid():
    c = Constraint(kind="budget", key="price", op="lte", value=40000.0, raw_text="40k")
    assert c.kind == "budget"


def test_constraint_invalid_kind_raises():
    with pytest.raises(ValidationError):
        Constraint(kind="unknown_kind", key="x", op="eq", value="y", raw_text="y")


def test_constraint_ext_preserved():
    c = Constraint(
        kind="must_have", key="ports.hdmi", op="eq",
        value="yes", raw_text="needs HDMI",
        ext={"confidence": 0.9},
    )
    assert c.ext["confidence"] == 0.9


def test_constraint_json_round_trip():
    c = Constraint(kind="budget", key="price", op="lte", value=40000.0, raw_text="40k")
    restored = Constraint.model_validate_json(c.model_dump_json())
    assert restored == c


# ---------------------------------------------------------------------------
# ParsedQuery
# ---------------------------------------------------------------------------

def test_parsed_query_defaults():
    q = ParsedQuery(language="en", query_en="laptop for video editing")
    assert q.hard == []
    assert q.needs_clarification is False


def test_parsed_query_with_hinglish():
    q = ParsedQuery(
        language="hinglish",
        query_en="laptop for video editing under 40000",
        budget=Budget(max_inr=40000),
        use_case="video editing",
    )
    assert q.language == "hinglish"
    assert q.budget.max_inr == 40000


def test_parsed_query_json_round_trip():
    q = ParsedQuery(language="en", query_en="gaming laptop")
    restored = ParsedQuery.model_validate_json(q.model_dump_json())
    assert restored == q


# ---------------------------------------------------------------------------
# EvidenceRef
# ---------------------------------------------------------------------------

def test_evidence_ref_valid():
    e = EvidenceRef(id="spec:P001:4", kind="spec_line", product_id="P001",
                    text="RAM: 16 GB DDR5")
    assert e.kind == "spec_line"


def test_evidence_ref_invalid_kind_raises():
    with pytest.raises(ValidationError):
        EvidenceRef(id="x:1", kind="unknown_kind", product_id="P1", text="t")


def test_evidence_ref_ext_preserved():
    e = EvidenceRef(id="rev:R1", kind="review", product_id="P1",
                    text="Great battery.", ext={"source": "scrape"})
    assert e.ext["source"] == "scrape"


def test_evidence_ref_json_round_trip():
    e = EvidenceRef(id="img:P001:2:a", kind="image_obs", product_id="P001",
                    text="Has HDMI port visible")
    restored = EvidenceRef.model_validate_json(e.model_dump_json())
    assert restored == e


# ---------------------------------------------------------------------------
# ReviewFlag
# ---------------------------------------------------------------------------

def test_review_flag_valid():
    f = ReviewFlag(review_id="R1", score=0.85,
                   signals={"near_dup": 0.9, "burst": 0.0},
                   reasons=["nearly identical to R2"],
                   action="exclude")
    assert f.action == "exclude"


def test_review_flag_action_invalid_raises():
    with pytest.raises(ValidationError):
        ReviewFlag(review_id="R1", score=0.5, signals={}, reasons=[], action="unknown")


# ---------------------------------------------------------------------------
# ScoreBreakdown
# ---------------------------------------------------------------------------

def test_score_breakdown_vision_none():
    s = _score(visual=None)
    assert s.visual is None


def test_score_breakdown_ext_preserved():
    s = _score(ext={"dummy_signal": 0.42})
    assert s.ext["dummy_signal"] == 0.42


def test_score_breakdown_json_round_trip():
    s = _score()
    restored = ScoreBreakdown.model_validate_json(s.model_dump_json())
    assert restored == s


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------

def test_recommendation_confidence_literals():
    for conf in ("high", "medium", "low"):
        r = _recommendation(confidence=conf)
        assert r.confidence == conf


def test_recommendation_invalid_confidence_raises():
    with pytest.raises(ValidationError):
        _recommendation(confidence="very_high")


# ---------------------------------------------------------------------------
# AdvisorResponse
# ---------------------------------------------------------------------------

def test_advisor_response_ok():
    r = _response()
    assert r.status == "ok"
    assert len(r.recommendations) == 1


def test_advisor_response_degraded():
    r = _response(status="degraded_ok", degraded=["vision_skipped:rate_limit"])
    assert "vision_skipped:rate_limit" in r.degraded


def test_advisor_response_abstained():
    r = _response(status="abstained", recommendations=[], message="No match found.")
    assert r.status == "abstained"
    assert r.recommendations == []


def test_advisor_response_manifest_stamped():
    """RunManifest can be stamped onto AdvisorResponse.manifest."""
    manifest = RunManifest(
        trace_id="trace-001",
        config_hash="abc" * 21 + "a",  # 64 chars
        profile="dev",
    )
    r = _response(manifest=manifest.to_dict())
    assert r.manifest is not None
    assert r.manifest["profile"] == "dev"
    assert r.manifest["trace_id"] == "trace-001"


def test_advisor_response_json_round_trip():
    r = _response()
    restored = AdvisorResponse.model_validate_json(r.model_dump_json())
    assert restored.status == r.status
    assert restored.trace_id == r.trace_id


# ---------------------------------------------------------------------------
# ToolResult[T]
# ---------------------------------------------------------------------------

def test_tool_result_ok():
    result: ToolResult[list[str]] = ToolResult(ok=True, data=["P001", "P002"],
                                               cost=ToolCost(model_calls=1, ms=320))
    assert result.ok
    assert result.data == ["P001", "P002"]


def test_tool_result_error():
    result: ToolResult[None] = ToolResult(ok=False, error="timeout", degraded=True)
    assert not result.ok
    assert result.degraded
    assert result.error == "timeout"


def test_tool_result_json_round_trip():
    result: ToolResult[dict] = ToolResult(ok=True, data={"k": "v"})
    restored = ToolResult.model_validate_json(result.model_dump_json())
    assert restored.ok
    assert restored.data == {"k": "v"}


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

def test_verdict_continue():
    v = Verdict(verifier="parse_ok", passed=True, action="continue")
    assert v.passed


def test_verdict_replan():
    v = Verdict(verifier="retrieval_nonempty", passed=False, action="replan",
                reason="zero results")
    assert v.action == "replan"


def test_verdict_invalid_action_raises():
    with pytest.raises(ValidationError):
        Verdict(verifier="x", passed=True, action="do_magic")


# ---------------------------------------------------------------------------
# GuardResult
# ---------------------------------------------------------------------------

def test_guard_result_passed():
    g = GuardResult(guardrail="pii_pre", stage="pre", passed=True)
    assert g.stage == "pre"


def test_guard_result_failed_pii():
    g = GuardResult(guardrail="pii_pre", stage="pre", passed=False,
                    threat="pii", detail="phone number detected")
    assert g.threat == "pii"


def test_guard_result_invalid_stage_raises():
    with pytest.raises(ValidationError):
        GuardResult(guardrail="x", stage="mid", passed=True)
