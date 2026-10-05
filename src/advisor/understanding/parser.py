"""Query understanding module (§5.3)."""
import re

from advisor.core.prompts import load_prompt
from advisor.core.registries import _BUILTIN_CONSTRAINT_KINDS, constraint_kinds
from advisor.core.schemas import Budget, ParsedQuery
from advisor.llm.gateway import Gateway


def fallback_parser(query: str) -> ParsedQuery:
    """Rule-based fallback parser when LLM is unavailable."""
    pq = ParsedQuery(language="en", query_en=query)
    m = re.search(r'(under|below)\s*(rs\.?|inr|₹)?\s*([\d,\.]+)\s*(k|lakh|lac|hazaar)?', query, re.I)
    if m:
        num = float(m.group(3).replace(',', ''))
        multiplier = 1
        suffix = (m.group(4) or "").lower()
        if suffix == 'k' or suffix == 'hazaar': multiplier = 1000
        elif suffix in ('lakh', 'lac'): multiplier = 100000
        pq.budget.max_inr = num * multiplier
    return pq

def cross_check_budget(query: str, budget: Budget):
    """Regex budget cross-check."""
    m_k = re.search(r'(\d+(?:\.\d+)?)\s*k\b', query, re.I)
    m_lakh = re.search(r'(\d+(?:\.\d+)?)\s*(lakh|lac)s?\b', query, re.I)
    m_hazaar = re.search(r'(\d+(?:\.\d+)?)\s*hazaar\b', query, re.I)

    val = None
    if m_lakh: val = float(m_lakh.group(1)) * 100000
    elif m_k: val = float(m_k.group(1)) * 1000
    elif m_hazaar: val = float(m_hazaar.group(1)) * 1000

    if val is not None and budget.max_inr is None:
        budget.max_inr = val

def validate_category(pq: ParsedQuery, valid_categories: set[str], valid_subcats: set[str] = None):
    # If the LLM put a valid subcategory in the 'category' field, allow it.
    is_valid = pq.category and pq.category in valid_categories
    if pq.category and not is_valid and valid_subcats:
        if any(pq.category.lower() in sub.lower() for sub in valid_subcats):
            is_valid = True

    if pq.category and not is_valid:
        pq.category = None

    # Never strip the subcategory if it's provided, as it is our best chance for a LIKE match
    pass

def validate_constraints(pq: ParsedQuery, spec_vocab: set[str]):
    valid_kinds = set(constraint_kinds.all_names()) | _BUILTIN_CONSTRAINT_KINDS
    valid = []
    for c in pq.hard:
        if c.kind not in valid_kinds:
            continue
        valid.append(c)
    pq.hard = valid

def parse_query(gateway: Gateway, query: str, taxonomy_list: str, valid_categories: set[str], spec_vocab: set[str] = None, tracer=None) -> ParsedQuery:
    """Parse query using LLM and fallback to deterministic rules."""
    import time
    t_start_format = time.time()
    prompt_tpl = load_prompt("parser")
    prompt = prompt_tpl.text.replace("{{taxonomy_list}}", taxonomy_list).replace("{{query}}", query)
    t_format = time.time() - t_start_format

    try:
        t_start_call = time.time()
        resp = gateway.call(
            role="parser",
            prompt=prompt,
            schema=ParsedQuery,
            tracer=tracer
        )
        t_call = time.time() - t_start_call
        if tracer:
            with tracer.span("tool_call", name="parse_query_inner") as s:
                s.output_summary = f"format={t_format:.2f}s call={t_call:.2f}s"

        if not resp.structured_data:
            raise ValueError("No data returned")
        pq = resp.structured_data
    except Exception as e:
        print("EXCEPTION IN PARSE_QUERY:", repr(e))
        pq = fallback_parser(query)

    cross_check_budget(query, pq.budget)
    validate_category(pq, valid_categories)
    validate_constraints(pq, spec_vocab or set())

    from advisor.understanding.clarify import apply_ambiguity_rule
    apply_ambiguity_rule(pq)

    return pq
