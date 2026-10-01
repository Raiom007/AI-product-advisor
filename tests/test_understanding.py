import pytest
from advisor.understanding.parser import fallback_parser, parse_query, cross_check_budget
from advisor.understanding.clarify import apply_ambiguity_rule, merge_clarification
from advisor.core.schemas import ParsedQuery, Budget, Constraint
from advisor.llm.gateway import Gateway
from advisor.core.config import load_config

def test_fallback_parser_extracts_budget():
    pq = fallback_parser("gaming laptop under 50k")
    assert pq.budget.max_inr == 50000.0
    
    pq2 = fallback_parser("phone below 1.5 lakh")
    assert pq2.budget.max_inr == 150000.0

def test_cross_check_budget():
    budget = Budget()
    cross_check_budget("I have 40 hazaar", budget)
    assert budget.max_inr == 40000.0

def test_ambiguity_rule_no_category():
    pq = ParsedQuery(language="en", query_en="hello")
    apply_ambiguity_rule(pq)
    assert pq.needs_clarification
    assert "What kind" in pq.clarifying_question

def test_ambiguity_rule_contradictory_budget():
    pq = ParsedQuery(language="en", query_en="laptop", category="Laptops")
    pq.budget.min_inr = 50000.0
    pq.budget.max_inr = 40000.0
    apply_ambiguity_rule(pq)
    assert pq.needs_clarification
    assert "Which one is correct" in pq.clarifying_question

def test_merge_clarification():
    prev = ParsedQuery(language="en", query_en="I want a laptop", category="Laptops")
    prev.budget.min_inr = 50000.0
    prev.budget.max_inr = 40000.0
    apply_ambiguity_rule(prev)
    assert prev.needs_clarification
    
    new = ParsedQuery(language="en", query_en="I mean 60000 max")
    new.budget.max_inr = 60000.0
    
    merged = merge_clarification(prev, new)
    assert merged.budget.max_inr == 60000.0
    assert not merged.needs_clarification

def test_parse_query_with_fake_provider():
    config = load_config()
    models_config = config.get("models", {})
    for role in models_config.get("roles", {}):
        models_config["roles"][role]["candidates"] = ["fake/fake-1"]
    gateway = Gateway(models_config=models_config, limits_config=config.get("limits", {}))
    
    # The fake provider returns an empty constructed schema. The fallback parser will thus be triggered.
    # No, wait, if the fake provider returns an empty ParsedQuery, the fallback isn't triggered, 
    # but the budget cross_check will run!
    pq = parse_query(gateway, "laptop under 40k", "Laptops", {"Laptops"})
    assert pq.budget.max_inr == 40000.0 # Thanks to cross check
