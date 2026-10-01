"""Ambiguity rule (§5.3)."""
from advisor.core.schemas import ParsedQuery

def apply_ambiguity_rule(pq: ParsedQuery):
    """Set needs_clarification and clarifying_question if ambiguous."""
    contradictory_budget = False
    if pq.budget.min_inr is not None and pq.budget.max_inr is not None:
        if pq.budget.min_inr > pq.budget.max_inr:
            contradictory_budget = True

    if not pq.category and not pq.use_case:
        pq.needs_clarification = True
        pq.clarifying_question = "What kind of product are you looking for, or how do you plan to use it?"
    elif contradictory_budget:
        pq.needs_clarification = True
        pq.clarifying_question = f"You mentioned a minimum budget of {pq.budget.min_inr} and a maximum of {pq.budget.max_inr}. Which one is correct?"
    else:
        pq.needs_clarification = False
        pq.clarifying_question = None

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
    apply_ambiguity_rule(prev)
    return prev
