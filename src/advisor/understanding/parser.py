"""Query understanding module (§5.3)."""
import re

from advisor.core.prompts import load_prompt
from advisor.core.registries import _BUILTIN_CONSTRAINT_KINDS, constraint_kinds
from advisor.core.schemas import Budget, ParsedQuery
from advisor.llm.gateway import Gateway

# WHY: cheap safety net so degraded mode never returns SIM cards for "phone"
# (by forcing subcategory="Cell Phones") or books for "laptop". Values must
# match cat_l1 and cat_l2 values present in the products table.
_KEYWORD_CATEGORY_MAP: list[tuple[str, str, str | None]] = [
    # kw, cat_l1, subcategory (mapped against l2 or l3 in filters.py)
    ("gaming laptop",           "Electronics", "Computers & Tablets"),
    ("smartwatch",              "Electronics", "Wearable Technology"),
    ("smart watch",             "Electronics", "Wearable Technology"),
    ("smartphone",              "Cell Phones & Accessories", "Cell Phones"),
    ("headphone",               "Electronics", "Headphones, Earbuds & Accessories"),
    ("earphone",                "Electronics", "Headphones, Earbuds & Accessories"),
    ("earbud",                  "Electronics", "Headphones, Earbuds & Accessories"),
    # single-word stems
    ("phone",                   "Cell Phones & Accessories", "Cell Phones"),
    ("mobile",                  "Cell Phones & Accessories", "Cell Phones"),
    ("laptop",                  "Electronics", "Computers & Tablets"),
    ("tablet",                  "Electronics", "Computers & Tablets"),
    ("camera",                  "Electronics", "Camera & Photo"),
    ("monitor",                 "Electronics", "Computers & Accessories"),
    ("tv",                      "Electronics", "Television & Video"),
    ("television",              "Electronics", "Television & Video"),
    ("router",                  "Electronics", "Computers & Accessories"),
    ("speaker",                 "Electronics", "Home Audio"),
    ("watch",                   "Electronics", "Wearable Technology"),
    ("mouse",                   "Electronics", "Computers & Accessories"),
    ("keyboard",                "Electronics", "Computers & Accessories"),
]


def fallback_parser(query: str) -> ParsedQuery:
    """Rule-based fallback parser when LLM is unavailable.

    WHY: the LLM parser may be offline (quota exhausted, network block).
    This deterministic fallback extracts two signals that dramatically
    improve degraded-mode quality without any model call:
      1. budget — existing regex for under/below + unit suffix.
      2. category — keyword scan using _KEYWORD_CATEGORY_MAP so the
         retriever receives a category hard-constraint and BM25 cannot
         match "Chinese phone number" for a phone query (SOW §5.1).
    """
    pq = ParsedQuery(language="en", query_en=query)

    # 1. Budget extraction (existing logic, unchanged)
    if "no limit" in query.lower() or "unlimited" in query.lower():
        pq.budget.max_inr = 999999999.0
    else:
        m = re.search(r'(under|below)\s*(rs\.?|inr|₹)?\s*([\d,\.]+)\s*(k|lakh|lac|hazaar)?', query, re.I)
        if m:
            num = float(m.group(3).replace(',', ''))
            suffix = (m.group(4) or "").lower()
            multiplier = 1000 if suffix in ('k', 'hazaar') else (100000 if suffix in ('lakh', 'lac') else 1)
            pq.budget.max_inr = num * multiplier

    # 2. Category extraction — first keyword match wins (longest match listed first)
    q_lower = query.lower()
    for kw, cat, subcat in _KEYWORD_CATEGORY_MAP:
        if kw in q_lower:
            pq.category = cat
            pq.subcategory = subcat
            break  # first match wins; list is ordered by specificity

    # 3. Use-case extraction
    common_use_cases = [
        "gaming", "coding", "programming", "office", "work", "college", 
        "student", "editing", "browsing", "home", "photography", "business", 
        "music", "gym", "reading", "drawing", "travel", "wildlife", "outdoors",
        "daily use", "calls", "social media", "studio", "portrait", "videography",
        "street", "movies", "streaming", "sports", "smart home", "wfh"
    ]
    for uc in common_use_cases:
        if uc in q_lower:
            pq.use_case = uc
            break

    # 4. Basic hard constraint extraction (Size/Screen)
    # E.g. "15-16 inch", "14 inch"
    m_size = re.search(r'(\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?)\s*(inch|in\b|")', query, re.I)
    if m_size:
        from advisor.core.schemas import Constraint
        pq.hard.append(Constraint(
            kind="size_limit",
            key="screen_size",
            op="contains",
            value=f"{m_size.group(1)} inch",
            raw_text=m_size.group(0)
        ))

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

def parse_query(
    gateway: Gateway,
    query: str,
    taxonomy_list: str = "",
    valid_categories: set[str] = None,
    valid_subcats: set[str] = None,
    spec_vocab: set[str] = None,
    tracer=None,
    chat_history: list[dict] = None,
) -> ParsedQuery:
    """Parse query using LLM and fallback to deterministic rules."""
    import time
    t_start_format = time.time()
    prompt_tpl = load_prompt("parser")
    
    if isinstance(taxonomy_list, list) and chat_history is None:
        chat_history = taxonomy_list
        taxonomy_list = ""

    history_str = ""
    if chat_history and isinstance(chat_history, list):
        history_lines = []
        for msg in chat_history:
            if isinstance(msg, dict):
                role = msg.get("role", "unknown")
                if role == "user":
                    history_lines.append(f"User: {msg.get('content')}")
                elif role == "assistant":
                    history_lines.append(f"Assistant: {msg.get('content')}")
        history_str = "\n".join(history_lines) + "\n\n"
        
    prompt = prompt_tpl.text.replace("{{taxonomy_list}}", taxonomy_list).replace("{{query}}", history_str + "Current Query: " + query)
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

    # WHY: The LLM parser frequently extracts category="Cell Phones & Accessories"
    # but fails to specify subcategory="Cell Phones", OR it extracts an invalid category.
    # This allows SIM Cards to match phone queries. Augment with the keyword map
    # BEFORE validate_category clears invalid categories.
    print(f"DEBUG pre-aug: cat={pq.category} sub={pq.subcategory}")
    is_subcat_valid = False
    if pq.subcategory and valid_subcats:
        if any(pq.subcategory.lower() in sub.lower() for sub in valid_subcats):
            is_subcat_valid = True

    q_lower = query.lower()
    q_en_lower = (pq.query_en or "").lower()
    for kw, cat, subcat in _KEYWORD_CATEGORY_MAP:
        # Match word boundaries or simple substring
        if kw in q_lower or kw in q_en_lower:
            print(f"DEBUG matched kw '{kw}' -> setting cat={cat} sub={subcat}")
            pq.category = cat
            pq.subcategory = subcat
            is_subcat_valid = True
            break

    validate_category(pq, valid_categories, valid_subcats)
    validate_constraints(pq, spec_vocab or set())

    from advisor.understanding.clarify import apply_ambiguity_rule
    if not (chat_history and not pq.needs_clarification):
        apply_ambiguity_rule(pq)
    print(f"DEBUG post-aug: cat={pq.category} sub={pq.subcategory}")

    return pq
