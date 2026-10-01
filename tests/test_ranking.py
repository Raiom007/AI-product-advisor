import pytest
import math
from advisor.ranking.scorer import score_product, gate, rank_candidates
from advisor.ranking.explain_rank import explain_pairwise

# Provide dummy signals for test isolation if needed, or use the real ones.
# Actually, the real ones just look at dict keys.

def test_weights_sum_to_one_and_renormalisation():
    product = {
        "rrf_score": 0.8,
        "soft_prefs_satisfied": ["a"],
        "visual_checks": [] # This gives visual=0.5
    }
    context = {
        "min_rrf": 0.0, "max_rrf": 1.0,
        "total_soft_prefs": 2,
        "vision_skipped": False
    }
    
    brk, total = score_product(product, context)
    
    # weights sum to 1
    assert math.isclose(sum(brk.weights_used.values()), 1.0)
    assert brk.visual is not None
    assert "visual" in brk.weights_used
    
    # Now simulate vision_skipped
    context["vision_skipped"] = True
    brk2, total2 = score_product(product, context)
    
    assert brk2.visual is None
    assert "visual" not in brk2.weights_used
    assert math.isclose(sum(brk2.weights_used.values()), 1.0)
    # The weights for relevance, soft_fit, etc. should be higher now
    assert brk2.weights_used["relevance"] > brk.weights_used["relevance"]

def test_gate_never_lets_violator_through():
    p_good = {"id": "P1", "violates_hard_constraints": False}
    p_bad = {"id": "P2", "violates_hard_constraints": True}
    
    shortlist = [p_good, p_bad]
    
    # We must ensure gating drops p_bad.
    # The gate function is tested directly
    assert gate(p_good, []) is True
    assert gate(p_bad, []) is False
    
    # And through rank_candidates
    final = rank_candidates(shortlist, {}, [])
    assert len(final) == 1
    assert final[0]["id"] == "P1"

def test_pairwise_contributions_sum_exactly_to_diff():
    # Setup two products that have been scored
    p_a = {
        "id": "PA", "rrf_score": 1.0, "soft_prefs_satisfied": ["a","b"], "visual_checks": [{"verdict": "agree"}]
    }
    p_b = {
        "id": "PB", "rrf_score": 0.5, "soft_prefs_satisfied": ["a"], "visual_checks": [{"verdict": "disagree"}]
    }
    context = {"min_rrf": 0.0, "max_rrf": 1.0, "total_soft_prefs": 2, "vision_skipped": False}
    
    # Ensure they have score_breakdown
    brk_a, tot_a = score_product(p_a, context)
    p_a["score_breakdown"] = brk_a
    brk_b, tot_b = score_product(p_b, context)
    p_b["score_breakdown"] = brk_b
    
    diff_expected = tot_a - tot_b
    
    contributions = explain_pairwise(p_a, p_b)
    sum_contrib = sum(c["contribution"] for c in contributions)
    
    assert math.isclose(sum_contrib, diff_expected, rel_tol=1e-6)
    
    # Should be sorted descending
    assert contributions[0]["contribution"] >= contributions[-1]["contribution"]
