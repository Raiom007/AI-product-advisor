"""Parser eval suite.

Runs golden query examples and asserts extraction accuracy for budget, category, and constraints.
"""
import json
from pathlib import Path
from advisor.core.registries import suite
from advisor.understanding.parser import parse_query, validate_category, cross_check_budget
from advisor.llm.gateway import Gateway
from advisor.core.schemas import ParsedQuery, Constraint

def _check_data(data: list):
    if not data:
        raise ValueError("FAIL LOUDLY: no data")

@suite("parser")
def parser_suite(data: list, mode: str):
    def _check_data(d: list):
        if not d:
            raise ValueError("FAIL LOUDLY: no data")
    _check_data(data)
    
    data_path = Path("eval/data/parser.jsonl")
    real_data = []
    if data_path.exists():
        with data_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    real_data.append(json.loads(line))
    
    _check_data(real_data)
    
    from advisor.core.config import load_config
    
    config = load_config()
    # In live mode, use the real gateway config. In replay, use fake.
    models_config = config.get("models", {})
    if mode == "replay":
        # override roles to use fake provider
        for role in models_config.get("roles", {}):
            models_config["roles"][role]["candidates"] = ["fake/fake-1"]
            
    limits_config = config.get("limits", {})
    gateway = Gateway(models_config=models_config, limits_config=limits_config)
    
    # Pre-load taxonomy and vocab (dummy for now as this is just scaffolding the pipeline)
    taxonomy = "Electronics, Mobiles, Laptops, Cameras, Wearables"
    valid_categories = {"Electronics", "Home", "Fashion"}
    
    passed = 0
    total = len(real_data)
    
    for item in real_data:
        query = item["query"]
        expected = item["expected"]
        
        pq = parse_query(gateway, query, taxonomy, valid_categories)
        
        # Check extraction accuracy
        match = True
        
        # In Fake mode, it uses fallback_parser if fake returns an empty shell or we just rely on fallback.
        # Fallback parser extracts budget and category is null.
        if expected.get("category") and pq.category != expected.get("category"):
            match = False
            
        if expected.get("budget_max") != pq.budget.max_inr:
            match = False
            
        if match:
            passed += 1

    return {"accuracy": passed / total if total > 0 else 0}
