"""Renderer — inserts REAL review text and REAL spec lines by id.

The LLM never types a quote. The renderer fetches evidence by id from the
pool and splices the actual stored text into the Recommendation output.
This is the §5.7 grounding guarantee enforced structurally, not by prompt.
"""
from __future__ import annotations

import logging
from advisor.core.schemas import Recommendation, ScoreBreakdown

logger = logging.getLogger(__name__)


def render_recommendation(
    product_id: str,
    rank: int,
    statements: list[dict],
    review_quote_ids: list[str],
    image_obs_ids: list[str],
    evidence_pool: list[dict],
    score: ScoreBreakdown,
    confidence: str,
) -> Recommendation:
    """Build a Recommendation, splicing real evidence text for quotes.

    WHY: The LLM returns evidence IDs only. This function inserts the real,
    stored text so the final output is provably from the DB, not invented.
    """
    id_to_ev: dict[str, dict] = {ev["id"]: ev for ev in evidence_pool if "id" in ev}

    # Build the paragraph: join statement texts (they have already been validated).
    paragraph = " ".join(s["text"] for s in statements) if statements else _template_paragraph(evidence_pool)

    # Resolve review quote evidence ids to their real text (stored in the pool)
    rendered_quotes: list[str] = []
    for rid in review_quote_ids:
        ev = id_to_ev.get(rid)
        if ev:
            text = ev.get("text", "")
            meta = ev.get("meta", {})
            rating = meta.get("rating", "?")
            date = meta.get("date", "")
            # Format: "★4 (2024-01-01): Great battery life."
            rendered_quotes.append(f"★{rating} ({date}): {text}")
        else:
            logger.warning(f"render: review evidence id '{rid}' not found in pool")

    # Resolve image obs ids
    rendered_obs: list[str] = []
    for iid in image_obs_ids:
        ev = id_to_ev.get(iid)
        if ev:
            rendered_obs.append(ev.get("text", ""))

    return Recommendation(
        product_id=product_id,
        rank=rank,
        paragraph=paragraph,
        statements=statements,
        constraint_evidence={},   # populated by the constraint gate in P18+ pass
        review_quotes=rendered_quotes,
        image_observations=rendered_obs,
        score=score,
        confidence=confidence,
    )


def _template_paragraph(evidence_pool: list[dict]) -> str:
    """Template fallback paragraph — purely extractive, no LLM.

    Labelled 'Basic explanation mode' as per §7 degradation ladder.
    """
    spec_lines = [
        ev["text"] for ev in evidence_pool if ev.get("kind") == "spec_line"
    ][:3]
    if spec_lines:
        return "[Basic explanation mode] Key specs: " + "; ".join(spec_lines) + "."
    return "[Basic explanation mode] No detailed specs available."


# ── Template fallback for full Recommendation ────────────────────────────────

def template_recommendation(
    product_id: str,
    rank: int,
    evidence_pool: list[dict],
    score: ScoreBreakdown,
    confidence: str,
) -> Recommendation:
    """Fully extractive Recommendation — used when composer LLM is unavailable."""
    paragraph = _template_paragraph(evidence_pool)

    # Pick the top-rated and lowest-rated review ids for quotes
    reviews = [ev for ev in evidence_pool if ev.get("kind") == "review"]
    reviews_by_rating = sorted(
        reviews, key=lambda e: e.get("meta", {}).get("rating", 3), reverse=True
    )
    top_ids = [r["id"] for r in reviews_by_rating[:2]]
    bot_ids = [r["id"] for r in reviews_by_rating[-1:] if reviews_by_rating[-1]["id"] not in top_ids]
    quote_ids = (top_ids + bot_ids)[:4]

    return render_recommendation(
        product_id=product_id,
        rank=rank,
        statements=[],
        review_quote_ids=quote_ids,
        image_obs_ids=[],
        evidence_pool=evidence_pool,
        score=score,
        confidence=confidence,
    )


# ── Abstention output ────────────────────────────────────────────────────────

def make_abstention_response(reason: str, config: dict | None = None) -> dict:
    """Build the abstention message dict.

    config flag 'nearest_alternatives' (default False) controls whether
    to show closest non-matching products (open question §12).
    Per Hemanth's standing instruction: default is strict refuse.
    """
    cfg = config or {}
    show_nearest = cfg.get("nearest_alternatives", False)

    msg = f"No product fully meets your request. {reason}"
    if not show_nearest:
        msg += " Please broaden your filters or adjust your budget."

    return {
        "status": "abstained",
        "message": msg,
        "show_nearest_alternatives": show_nearest,
    }
