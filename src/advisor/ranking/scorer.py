"""Ranking and scoring logic (§5.6)."""
from typing import List, Dict, Any, Tuple
import math
import advisor.ranking.signals # ensures decorators run
from advisor.core.schemas import ScoreBreakdown
from advisor.core.config import load_config
from advisor.core.registries import ranking_signals

def gate(product: dict, constraints: list) -> bool:
    """Hard constraints gate. 1 if satisfies all, else 0."""
    violates = product.get("violates_hard_constraints", False)
    if violates:
        return False
        
    for c in constraints:
        # Evaluate real constraints here
        pass
    return True

def score_product(product: dict, context: dict) -> Tuple[ScoreBreakdown, float]:
    """Score a product using registered signals and configured weights.
    
    Drops None signals (like visual when skipped) and renormalizes.
    Returns (ScoreBreakdown, final_total)
    """
    config = load_config()
    weights_conf = config.get("ranking", {}).get("weights", {
        "relevance": 0.30,
        "soft_fit": 0.15,
        "use_case_sentiment": 0.30,
        "review_trust": 0.15,
        "visual": 0.10
    })
    
    raw_scores = {}
    valid_weights = {}
    
    for sig_name, w in weights_conf.items():
        if sig_name not in ranking_signals.all_names():
            continue
            
        sig_fn = ranking_signals.get(sig_name)
        val = sig_fn(product, context)
        
        if val is not None:
            raw_scores[sig_name] = val
            valid_weights[sig_name] = w
            
    # Renormalize
    w_sum = sum(valid_weights.values())
    if w_sum > 0:
        renorm_weights = {k: v / w_sum for k, v in valid_weights.items()}
    else:
        renorm_weights = {}
        
    total = sum(raw_scores[k] * renorm_weights[k] for k in renorm_weights)
    
    breakdown = ScoreBreakdown(
        relevance=raw_scores.get("relevance", 0.0),
        soft_fit=raw_scores.get("soft_fit", 0.0),
        use_case_sentiment=raw_scores.get("use_case_sentiment", 0.0),
        review_trust=raw_scores.get("review_trust", 0.0),
        visual=raw_scores.get("visual", None),
        total=total,
        weights_used=renorm_weights
    )
    
    return breakdown, total

def tie_break_key(product: dict, score: float, context: dict) -> tuple:
    """Tie-break: score descending, then review_trust desc, then price asc.
    
    Since we sort ascending by this key, we negate desc values.
    """
    budget_max = context.get("budget_max_inr", float('inf'))
    price = product.get("price", 0)
    
    # Closer to budget ceiling is NOT preferred?
    # Usually handled by price asc anyway.
    trust = product.get("review_trust_val", 0.0) 
    # Try to grab it from precomputed or just use price
    
    return (-score, -trust, price)

def rank_candidates(shortlist: List[dict], context: dict, constraints: list) -> List[dict]:
    """Two-pass ranking flow.
    
    Pass 1 = Score without V -> pick top-N -> run vision -> Pass 2 = Score with V -> final.
    """
    # 1. Hard constraint gate
    gated = [p for p in shortlist if gate(p, constraints)]
    
    # Pre-compute min/max RRF for the context
    rrfs = [p.get("rrf_score", 0.0) for p in gated]
    if rrfs:
        context["min_rrf"] = min(rrfs)
        context["max_rrf"] = max(rrfs)
        
    # Pass 1: Pre-rank without vision
    # Temporarily force visual=None by setting vision_skipped
    orig_vision_skipped = context.get("vision_skipped", False)
    context["vision_skipped"] = True
    
    scored_pass_1 = []
    for p in gated:
        brk, tot = score_product(p, context)
        p["score_breakdown"] = brk
        p["pre_score"] = tot
        # Cache trust for tiebreak
        p["review_trust_val"] = brk.review_trust
        scored_pass_1.append(p)
        
    scored_pass_1.sort(key=lambda p: tie_break_key(p, p["pre_score"], context))
    
    # Vision step would happen here externally. In actual flow, Agent executor runs vision on top-N.
    # The Scorer assumes visual data is just present in `visual_checks` if the agent ran it.
    
    # Pass 2: Final rank (restore vision_skipped)
    context["vision_skipped"] = orig_vision_skipped
    
    final = []
    for p in scored_pass_1:
        brk, tot = score_product(p, context)
        p["score_breakdown"] = brk
        p["final_score"] = tot
        final.append(p)
        
    final.sort(key=lambda p: tie_break_key(p, p["final_score"], context))
    return final
