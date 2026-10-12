from advisor.core.config import load_config
from advisor.core.schemas import Budget, ParsedQuery
from advisor.llm.gateway import Gateway
from advisor.understanding.clarify import apply_ambiguity_rule, merge_clarification
from advisor.understanding.parser import cross_check_budget, fallback_parser, parse_query


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


# ── fallback_parser category map (item 1 / diagnostic fix) ───────────────────

def test_fallback_parser_phone_routes_to_cell_phones():
    """Core regression: "phone" must map to Cell Phones & Accessories in degraded mode.
    WHY: without this, BM25 matches 'Chinese phone number' (SIM card) for phone queries.
    """
    pq = fallback_parser("ek acha phone dikhana under 40k")
    assert pq.category == "Cell Phones & Accessories", (
        f"Expected 'Cell Phones & Accessories', got {pq.category!r}"
    )
    assert pq.budget.max_inr == 40000.0


def test_fallback_parser_smartphone_routes_to_cell_phones():
    pq = fallback_parser("best smartphone under 30000")
    assert pq.category == "Cell Phones & Accessories"


def test_fallback_parser_laptop_routes_to_electronics():
    pq = fallback_parser("gaming laptop under 80k")
    # "gaming laptop" is more specific and must beat bare "laptop" stem
    assert pq.category == "Electronics"


def test_fallback_parser_smartwatch_routes_to_electronics():
    pq = fallback_parser("good smartwatch under 15k")
    assert pq.category == "Electronics"
    assert pq.subcategory == "Wearable Technology"


def test_fallback_parser_tv_routes_to_electronics():
    pq = fallback_parser("4k tv under 50000")
    assert pq.category == "Electronics"


def test_fallback_parser_monitor_routes_to_electronics():
    pq = fallback_parser("27 inch monitor under 20k")
    assert pq.category == "Electronics"


def test_fallback_parser_router_routes_to_electronics():
    pq = fallback_parser("wifi router under 5000")
    assert pq.category == "Electronics"


def test_fallback_parser_speaker_routes_to_electronics():
    pq = fallback_parser("bluetooth speaker under 3k")
    assert pq.category == "Electronics"


def test_fallback_parser_mouse_routes_to_electronics():
    pq = fallback_parser("wireless mouse")
    assert pq.category == "Electronics"


def test_fallback_parser_keyboard_routes_to_electronics():
    pq = fallback_parser("mechanical keyboard under 5000")
    assert pq.category == "Electronics"


def test_fallback_parser_no_keyword_gives_no_category():
    """Ambiguous query with no known keyword must not force a wrong category."""
    pq = fallback_parser("something nice under 10k")
    assert pq.category is None


def test_fallback_parser_budget_unchanged_by_category_logic():
    """Category extraction must not corrupt the budget."""
    pq = fallback_parser("phone under 40 hazaar")
    assert pq.budget.max_inr == 40000.0
    assert pq.category == "Cell Phones & Accessories"

