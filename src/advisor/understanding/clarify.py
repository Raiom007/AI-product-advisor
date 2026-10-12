"""Ambiguity rule (§5.3)."""
from advisor.core.schemas import ParsedQuery


def apply_ambiguity_rule(pq: ParsedQuery):
    """Set needs_clarification and clarifying_question if ambiguous."""
    contradictory_budget = False
    if pq.budget.min_inr is not None and pq.budget.max_inr is not None:
        if pq.budget.min_inr > pq.budget.max_inr:
            contradictory_budget = True

    # WHY: Maps common subcategories to contextual use-case suggestions so the
    # clarification buttons feel relevant rather than generic.
    USE_CASE_MAP = {
        "laptop":    ["Gaming", "Coding / programming", "College / student use", "Video editing", "Everyday browsing"],
        "computer":  ["Gaming", "Coding / programming", "Office work", "Video editing", "Home use"],
        "phone":     ["Photography", "Gaming", "Daily use / calls", "Business", "Social media"],
        "camera":    ["Wildlife / outdoors", "Travel", "Studio / portrait", "Videography", "Street photography"],
        "tv":        ["Movies & streaming", "Gaming", "Sports watching", "Smart home hub"],
        "headphone": ["Music listening", "Gaming", "Work calls / WFH", "Gym / running"],
        "tablet":    ["Reading / studying", "Drawing / art", "Gaming", "Streaming videos"],
    }

    def _suggestions_for(pq: ParsedQuery) -> list[str]:
        combined = f"{(pq.subcategory or '')} {(pq.category or '')}".lower()
        for kw, options in USE_CASE_MAP.items():
            if kw in combined:
                return options
        return ["Daily / personal use", "Office / work", "Gaming", "Creative / media work"]

    if contradictory_budget:
        pq.needs_clarification = True
        pq.clarifying_question = f"You mentioned a minimum budget of {pq.budget.min_inr} and a maximum of {pq.budget.max_inr}. Which one is correct?"
        pq.suggested_answers = [f"Under {pq.budget.min_inr}", f"Around {pq.budget.max_inr}"]
    elif not pq.category and not pq.use_case:
        pq.needs_clarification = True
        pq.clarifying_question = "What kind of product are you looking for, or how do you plan to use it?"
        pq.suggested_answers = ["Laptop for coding", "Gaming PC", "Phone for photography"]
    elif pq.category and not pq.use_case and not pq.needs_clarification:
        # WHY: Category is known but intent is still ambiguous — knowing the use
        # case lets us rank results far more accurately (e.g. gaming vs student laptop).
        pq.needs_clarification = True
        product_label = (pq.subcategory or pq.category or "it").lower()
        # Clean up labels like "Computers & Tablets" for natural language
        if "&" in product_label: product_label = product_label.split("&")[0].strip()
        pq.clarifying_question = f"Nice! What will you use the {product_label} for?"
        pq.suggested_answers = _suggestions_for(pq)
    elif pq.budget.max_inr is None and not pq.needs_clarification:
        # WHY: Business rule dictates we MUST ask for budget if missing for every product.
        pq.needs_clarification = True
        pq.clarifying_question = "What is your budget limit for this?"
        pq.suggested_answers = ["Under ₹50,000", "Under ₹80,000", "No limit"]
    elif not pq.use_case and not pq.needs_clarification:
        # Specific follow-up questions per category when use_case is missing
        q_str = (pq.query_en or "").lower()
        product_label = (pq.subcategory or pq.category or "").lower()
        
        if "laptop" in product_label or "computer" in product_label:
            has_os = any(os in q_str for os in ["mac", "windows", "apple", "chrome", "no preference", "any"])
            if not has_os:
                pq.needs_clarification = True
                pq.clarifying_question = "Do you have a preference for Windows, Mac, or a Chromebook?"
                pq.suggested_answers = ["Windows", "Mac", "Chromebook", "No preference"]
            else:
                has_size = any(sz in q_str for sz in ["inch", "\"", "display", "screen", "size", "any size", "no preference", "any"])
                if not has_size:
                    pq.needs_clarification = True
                    pq.clarifying_question = "Any preference on the screen size?"
                    pq.suggested_answers = ["13-14 inch (Portable)", "15-16 inch (Standard)", "17+ inch (Large)", "Any size"]

        elif "phone" in product_label:
            has_os = any(os in q_str for os in ["ios", "android", "iphone", "apple", "no preference", "any"])
            if not has_os:
                pq.needs_clarification = True
                pq.clarifying_question = "Do you prefer Android or an iPhone?"
                pq.suggested_answers = ["Android", "iPhone", "No preference"]
            else:
                has_storage = any(st in q_str for st in ["gb", "storage", "memory"])
                if not has_storage:
                    pq.needs_clarification = True
                    pq.clarifying_question = "How much storage do you typically need?"
                    pq.suggested_answers = ["128GB (Standard)", "256GB (Lots of apps/photos)", "512GB+ (Power user)"]

        elif "tv" in product_label or "television" in product_label:
            has_size = any(sz in q_str for sz in ["inch", "\"", "size", "any"])
            if not has_size:
                pq.needs_clarification = True
                pq.clarifying_question = "What TV size are you looking for?"
                pq.suggested_answers = ["43 inch (Small room)", "55 inch (Standard)", "65+ inch (Home theater)"]
            else:
                has_tech = any(tc in q_str for tc in ["oled", "qled", "led", "not sure", "any"])
                if not has_tech:
                    pq.needs_clarification = True
                    pq.clarifying_question = "Any preference on display technology like OLED or QLED?"
                    pq.suggested_answers = ["OLED (Best contrast)", "QLED (Brightest)", "Standard LED (Budget)", "Not sure"]

        elif "headphone" in product_label or "earbud" in product_label:
            has_style = any(st in q_str for st in ["earbud", "over-ear", "in-ear", "on-ear"])
            if not has_style:
                pq.needs_clarification = True
                pq.clarifying_question = "Do you prefer over-ear headphones or in-ear earbuds?"
                pq.suggested_answers = ["Over-ear (Comfort/ANC)", "In-ear / Earbuds (Portable)"]
            else:
                has_anc = any(anc in q_str for anc in ["anc", "noise", "cancelling", "necessary"])
                if not has_anc:
                    pq.needs_clarification = True
                    pq.clarifying_question = "Is Active Noise Cancellation (ANC) important to you?"
                    pq.suggested_answers = ["Yes, must have ANC", "Not necessary"]

        elif "camera" in product_label:
            has_type = any(t in q_str for t in ["dslr", "mirrorless", "point and shoot", "traditional", "compact", "easy"])
            if not has_type:
                pq.needs_clarification = True
                pq.clarifying_question = "Are you looking for a DSLR, Mirrorless, or a simple Point-and-Shoot camera?"
                pq.suggested_answers = ["Mirrorless (Modern/Compact)", "DSLR (Traditional)", "Point and Shoot (Easy)"]

def merge_clarification(prev: ParsedQuery, new: ParsedQuery) -> ParsedQuery:
    """Merge the new answer's parsed query into the previous one."""
    if new.category:
        prev.category = new.category
    if new.subcategory:
        prev.subcategory = new.subcategory
    if new.use_case:
        prev.use_case = new.use_case

    # Simple overwrite if user clarified budget
    if new.budget.min_inr is not None or new.budget.max_inr is not None:
        if new.budget.min_inr is not None:
            prev.budget.min_inr = new.budget.min_inr
        if new.budget.max_inr is not None:
            prev.budget.max_inr = new.budget.max_inr

    prev.hard.extend(new.hard)
    prev.soft.extend(new.soft)

    # Re-evaluate
    contradictory_budget = False
    if prev.budget.min_inr is not None and prev.budget.max_inr is not None:
        if prev.budget.min_inr > prev.budget.max_inr:
            contradictory_budget = True

    if contradictory_budget:
        apply_ambiguity_rule(prev)
    else:
        prev.needs_clarification = False
        prev.clarifying_question = None
        prev.suggested_answers = []
    return prev
