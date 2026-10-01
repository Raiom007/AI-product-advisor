"""Ranking signals (§5.6)."""
from advisor.core.registries import ranking_signal

@ranking_signal("relevance")
def compute_relevance(product: dict, context: dict) -> float:
    """Min-max normalized RRF score.
    
    context must contain min_rrf and max_rrf from the shortlist.
    """
    rrf = product.get("rrf_score", 0.0)
    min_rrf = context.get("min_rrf", 0.0)
    max_rrf = context.get("max_rrf", 1.0)
    
    if max_rrf <= min_rrf:
        return 1.0 # If all scores are equal, treat them as fully relevant
    
    return max(0.0, min(1.0, (rrf - min_rrf) / (max_rrf - min_rrf)))

@ranking_signal("soft_fit")
def compute_soft_fit(product: dict, context: dict) -> float:
    """Weighted fraction of soft preferences satisfied."""
    soft_prefs = product.get("soft_prefs_satisfied", [])
    total_soft_prefs = context.get("total_soft_prefs", 1)
    
    if total_soft_prefs == 0:
        return 1.0 # If no soft prefs, everyone fits perfectly
        
    return min(1.0, len(soft_prefs) / total_soft_prefs)

@ranking_signal("visual")
def compute_visual(product: dict, context: dict) -> float | None:
    """Visual verification score.
    
    0.5 + 0.5*(agree - 2*disagree)/max(checked,1), clipped to [0,1].
    None if vision skipped.
    """
    if context.get("vision_skipped", False) or "visual_checks" not in product:
        return None
        
    checks = product["visual_checks"]
    if not checks:
        return 0.5
        
    agree = sum(1 for c in checks if c.get("verdict") == "agree")
    disagree = sum(1 for c in checks if c.get("verdict") == "disagree")
    checked = len(checks)
    
    score = 0.5 + 0.5 * (agree - 2 * disagree) / max(checked, 1)
    return max(0.0, min(1.0, score))
