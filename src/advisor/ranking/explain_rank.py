"""Explanation and confidence logic (§5.6)."""
from typing import Dict, List, Any
from advisor.core.schemas import ScoreBreakdown

def explain_pairwise(product_a: dict, product_b: dict) -> List[Dict[str, Any]]:
    """Explain why A is ranked above B.
    
    Returns a list of dicts: {"signal": name, "contribution": w*(A-B)}, sorted by contribution desc.
    """
    brk_a: ScoreBreakdown = product_a.get("score_breakdown")
    brk_b: ScoreBreakdown = product_b.get("score_breakdown")
    
    if not brk_a or not brk_b:
        return []
        
    weights = brk_a.weights_used
    
    a_scores = {
        "relevance": brk_a.relevance,
        "soft_fit": brk_a.soft_fit,
        "use_case_sentiment": brk_a.use_case_sentiment,
        "review_trust": brk_a.review_trust,
        "visual": brk_a.visual or 0.0
    }
    b_scores = {
        "relevance": brk_b.relevance,
        "soft_fit": brk_b.soft_fit,
        "use_case_sentiment": brk_b.use_case_sentiment,
        "review_trust": brk_b.review_trust,
        "visual": brk_b.visual or 0.0
    }
    
    contributions = []
    for sig, w in weights.items():
        diff = a_scores[sig] - b_scores[sig]
        contrib = w * diff
        contributions.append({"signal": sig, "contribution": contrib, "w": w, "diff": diff})
        
    # Sort by contribution descending
    contributions.sort(key=lambda x: x["contribution"], reverse=True)
    return contributions

def determine_confidence(top_products: List[dict], context: dict) -> str:
    """Determine confidence (high/medium/low) per §5.6.
    
    high if:
      - margin(top1, top2) > 0.15
      - >= 3 unflagged reviews
      - no visual/spec contradiction
      - nothing degraded
    low if:
      - any contradiction
      - thin evidence
      - degradation
    else medium.
    """
    if not top_products:
        return "low"
        
    degraded = context.get("degraded", [])
    if degraded:
        return "low"
        
    p1 = top_products[0]
    p1_reviews = p1.get("n_reviews_used", 0)
    
    # Check contradictions (stub: assume a flag exists)
    has_contradiction = p1.get("has_contradiction", False)
    if has_contradiction or p1_reviews < 1:
        return "low"
        
    if len(top_products) > 1:
        p2 = top_products[1]
        margin = p1.get("final_score", 0.0) - p2.get("final_score", 0.0)
    else:
        margin = 1.0 # only 1 product
        
    if margin > 0.15 and p1_reviews >= 3 and not has_contradiction:
        return "high"
        
    return "medium"
