"""Review summarization (§5.4)."""
from typing import Dict, List
import logging
from advisor.core.schemas import ReviewSummary, ReviewSummaryBatch
from advisor.llm.gateway import Gateway
from advisor.core.prompts import load_prompt
from advisor.core.budget import RequestBudget
from advisor.guardrails.untrusted import spotlight, spotlight_system_rule

logger = logging.getLogger(__name__)

def summarize_reviews(gateway: Gateway, query: str, batch: Dict[str, List[dict]], budget: RequestBudget) -> Dict[str, ReviewSummary]:
    """Summarize reviews for a batch of products.
    
    batch: {product_id: [review_dict, ...]} where review_dict has 'id', 'text', 'rating', etc.
    Max 15 reviews per product, already filtered/redacted.
    Batch size max 3 products.
    """
    if not batch:
        return {}

    content_parts = []
    product_review_ids = {} # {product_id: set([R1, R2, ...])}

    for prod_id, reviews in batch.items():
        if len(reviews) > 15:
            reviews = reviews[:15]
            
        prod_text = f"Product ID: {prod_id}\n\n"
        valid_ids = set()
        
        for i, r in enumerate(reviews):
            rid = f"R{i+1}"
            valid_ids.add(rid)
            r_text = f"[{rid}] Rating: {r.get('rating', '')}\nText: {r.get('text', '')}"
            prod_text += f"{r_text}\n\n"
            
        product_review_ids[prod_id] = valid_ids
        content_parts.append(spotlight(prod_text, label="untrusted_data"))

    reviews_content = "\n".join(content_parts)
    
    prompt_tpl = load_prompt("summarizer")
    prompt = prompt_tpl.text.replace("{{reviews_content}}", reviews_content)
    if query:
        prompt = f"User use-case/query: {query}\n\n" + prompt

    system = spotlight_system_rule()

    try:
        max_attempts = 2
        for attempt in range(max_attempts):
            resp = gateway.call(
                role="summarizer",
                prompt=prompt,
                system=system,
                schema=ReviewSummaryBatch,
                budget=budget
            )
            if not resp.structured_data:
                raise ValueError("No structured data returned")
            
            batch_res = resp.structured_data
            
            # Grounding validation: reject if any id not in input
            valid_summaries = {}
            is_valid = True
            error_msg = ""
            for summ in batch_res.summaries:
                pid = summ.product_id
                if pid not in product_review_ids:
                    is_valid = False
                    error_msg = f"Hallucinated product id {pid}"
                    break
                    
                valid_ids = product_review_ids[pid]
                
                for p in summ.praises + summ.complaints:
                    for rid in p.get("review_ids", []):
                        if rid not in valid_ids:
                            is_valid = False
                            error_msg = f"Hallucinated review id {rid} for product {pid}"
                            break
                
                for rid in summ.use_case_fit.get("review_ids", []):
                    if rid not in valid_ids:
                        is_valid = False
                        error_msg = f"Hallucinated review id {rid} for product {pid}"
                        break
                        
                if not is_valid:
                    break
                    
                summ.n_reviews_used = len(valid_ids)
                summ.n_flagged_excluded = 0 # Can be set by caller if they excluded some
                valid_summaries[pid] = summ
                
            if is_valid:
                return valid_summaries
                
            if attempt < max_attempts - 1:
                prompt += f"\n\nERROR: {error_msg}. You MUST ONLY use the exact review IDs provided in the untrusted_data text (e.g. R1, R2). Fix your response."
                if budget: budget.charge("summarizer", calls=1)
            else:
                raise ValueError(error_msg)
                
    except Exception as e:
        logger.warning(f"Summarizer failed: {e}. Falling back to extractive.")
        return _fallback_summarizer(batch)

def _fallback_summarizer(batch: Dict[str, List[dict]]) -> Dict[str, ReviewSummary]:
    """Extractive fallback: top-rated unflagged excerpts, templated, labelled 'excerpt-based'."""
    res = {}
    for pid, reviews in batch.items():
        if len(reviews) > 15:
            reviews = reviews[:15]
            
        # Top rated excerpts
        high_rated = [r for r in reviews if r.get("rating", 0) >= 4]
        low_rated = [r for r in reviews if r.get("rating", 0) <= 2]
        
        praises = []
        complaints = []
        
        if high_rated:
            praises.append({"point": f"Excerpt-based: {high_rated[0].get('text', '')[:100]}...", "review_ids": ["R1"]})
        if low_rated:
            complaints.append({"point": f"Excerpt-based: {low_rated[0].get('text', '')[:100]}...", "review_ids": ["R2"]})
            
        res[pid] = ReviewSummary(
            product_id=pid,
            praises=praises,
            complaints=complaints,
            use_case_fit={"verdict": "unknown", "review_ids": []},
            n_reviews_used=len(reviews),
            n_flagged_excluded=0
        )
    return res
