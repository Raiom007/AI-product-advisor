"""Use-case sentiment and review trust signals (§5.4).

All ranking signals must accept (product: dict, context: dict) -> float | None.
The underlying math helpers are left as standalone functions so tests can
call them directly with typed arguments.
"""
import math
from advisor.core.registries import ranking_signal


# ── math helpers (testable standalone) ──────────────────────────────────────

def _review_trust_score(
    reviews: list[dict], flags: dict[str, dict] | None = None
) -> float:
    """T = 1 - flagged_mass/total_mass, coverage-scaled."""
    if not reviews:
        return 0.5

    flags = flags or {}
    total_mass = len(reviews)
    flagged_mass = 0.0

    for r in reviews:
        rid = r.get("id")
        flag = flags.get(rid)
        if flag:
            action = flag.get("action", "keep")
            if action == "exclude":
                flagged_mass += 1.0
            elif action == "downweight":
                flagged_mass += 0.7

    t_raw = 1.0 - (flagged_mass / total_mass)
    coverage_factor = min(1.0, total_mass / 10.0)
    t_scaled = 0.5 + (t_raw - 0.5) * coverage_factor
    return max(0.0, min(1.0, t_scaled))


def _use_case_sentiment_score(
    reviews: list[dict],
    similarities: dict[str, float] | None = None,
    flags: dict[str, dict] | None = None,
    prior_mean: float = 0.7,
    prior_weight: float = 5.0,
) -> float:
    """U = trust-weighted use-case sentiment (Bayesian-shrunk)."""
    similarities = similarities or {}
    flags = flags or {}

    if not reviews:
        return prior_mean

    weighted_sum = 0.0
    weight_total = 0.0

    for r in reviews:
        rid = r.get("id")
        rating = r.get("rating", 3)
        helpful = r.get("helpful_votes", 0)

        sent = (rating - 1) / 4.0

        flag = flags.get(rid, {})
        action = flag.get("action", "keep")
        if action == "exclude":
            flag_weight = 0.0
        elif action == "downweight":
            flag_weight = 0.3
        else:
            flag_weight = 1.0

        sim = max(0.0, similarities.get(rid, 1.0))
        weight = sim * flag_weight * math.log1p(helpful)

        weighted_sum += sent * weight
        weight_total += weight

    final = (weighted_sum + prior_mean * prior_weight) / (weight_total + prior_weight)
    return max(0.0, min(1.0, final))


# ── registered signals (product, context) → float ───────────────────────────

@ranking_signal("review_trust")
def compute_review_trust(product: dict, context: dict) -> float:
    """Adapter: pulls reviews + flags from product/context dicts."""
    reviews = product.get("reviews", [])
    flags = context.get("flags", {})
    return _review_trust_score(reviews, flags)


@ranking_signal("use_case_sentiment")
def compute_use_case_sentiment(product: dict, context: dict) -> float:
    """Adapter: pulls reviews, similarities and flags from product/context dicts."""
    reviews = product.get("reviews", [])
    similarities = context.get("similarities", {})
    flags = context.get("flags", {})
    return _use_case_sentiment_score(reviews, similarities, flags)
