"""Tests for constraint gate and filters.

Covers:
  - Gate never returns a product that fails any hard constraint (property-like)
  - Each constraint kind: True / False / None paths
  - Unverifiable handling: exclude vs include policy
  - SQL allow-list builder
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from advisor.core.schemas import Constraint
from advisor.retrieval.constraint_checks import (
    check_brand_exclude,
    check_budget,
    check_category,
    check_must_have,
    check_size_limit,
    check_weight_limit,
    gate,
)
from advisor.retrieval.filters import build_allow_list
from advisor.store.sqlite_store import insert_products, open_db

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_constraint(**kwargs) -> Constraint:
    defaults = dict(kind="budget", key="price", op="lte", value=50000, raw_text="under 50k")
    defaults.update(kwargs)
    return Constraint(**defaults)


def _make_product(**kwargs) -> dict:
    base = {
        "product_id": "P001",
        "name": "HP Gaming Laptop",
        "brand": "HP",
        "cat_l1": "Electronics",
        "cat_l2": "Laptops",
        "cat_l3": "Gaming Laptop",
        "retail_price_inr": 80000.0,
        "discounted_price_inr": 72000.0,
        "effective_price_inr": 72000.0,
        "price_unknown": 0,
        "price_anomaly": 0,
        "description": "Great gaming laptop.",
        "specification_text": "RAM: 16GB | Weight: 1.8 kg | Display: 15.6 inch | Noise Cancellation: No",
        "image_urls": "",
        "image_url_count": 0,
        "image_url_broken": 0,
        "alias_ids": "[]",
        "is_canonical": 1,
        "ingested_at": "2026-01-01T00:00:00+00:00",
    }
    base.update(kwargs)
    return base


def _open_mem_db() -> sqlite3.Connection:
    return open_db(Path(":memory:"))


# ---------------------------------------------------------------------------
# Budget constraint
# ---------------------------------------------------------------------------

class TestBudgetConstraint:

    def test_within_budget_passes(self):
        p = _make_product(effective_price_inr=45000)
        c = _make_constraint(kind="budget", op="lte", value=50000)
        assert check_budget(p, c) is True

    def test_over_budget_fails(self):
        p = _make_product(effective_price_inr=55000)
        c = _make_constraint(kind="budget", op="lte", value=50000)
        assert check_budget(p, c) is False

    def test_exactly_at_budget_passes(self):
        p = _make_product(effective_price_inr=50000)
        c = _make_constraint(kind="budget", op="lte", value=50000)
        assert check_budget(p, c) is True

    def test_price_unknown_unverifiable(self):
        p = _make_product(effective_price_inr=None)
        c = _make_constraint(kind="budget", op="lte", value=50000)
        assert check_budget(p, c) is None

    def test_gte_passes(self):
        p = _make_product(effective_price_inr=30000)
        c = _make_constraint(kind="budget", key="price", op="gte", value=20000)
        assert check_budget(p, c) is True

    def test_between_passes(self):
        p = _make_product(effective_price_inr=35000)
        c = _make_constraint(kind="budget", key="price", op="between",
                              value={"min_inr": 20000, "max_inr": 50000})
        assert check_budget(p, c) is True

    def test_between_below_min_fails(self):
        p = _make_product(effective_price_inr=15000)
        c = _make_constraint(kind="budget", key="price", op="between",
                              value={"min_inr": 20000, "max_inr": 50000})
        assert check_budget(p, c) is False


# ---------------------------------------------------------------------------
# Category constraint
# ---------------------------------------------------------------------------

class TestCategoryConstraint:

    def test_exact_cat_l2_match(self):
        p = _make_product()
        c = _make_constraint(kind="category", key="category", op="eq", value="Laptops")
        assert check_category(p, c) is True

    def test_exact_cat_l3_match(self):
        p = _make_product()
        c = _make_constraint(kind="category", key="category", op="eq", value="Gaming Laptop")
        assert check_category(p, c) is True

    def test_wrong_category_fails(self):
        p = _make_product()
        c = _make_constraint(kind="category", key="category", op="eq", value="Smartphones")
        assert check_category(p, c) is False

    def test_no_category_unverifiable(self):
        p = _make_product(cat_l1=None, cat_l2=None, cat_l3=None)
        c = _make_constraint(kind="category", key="category", op="eq", value="Laptops")
        assert check_category(p, c) is None

    def test_in_operator_passes(self):
        p = _make_product()
        c = _make_constraint(kind="category", key="category", op="in",
                              value=["Laptops", "Tablets"])
        assert check_category(p, c) is True

    def test_case_insensitive(self):
        p = _make_product()
        c = _make_constraint(kind="category", key="category", op="eq", value="laptops")
        assert check_category(p, c) is True


# ---------------------------------------------------------------------------
# Brand exclude constraint
# ---------------------------------------------------------------------------

class TestBrandExclude:

    def test_not_excluded_brand_passes(self):
        p = _make_product(brand="Dell")
        c = _make_constraint(kind="brand_exclude", key="brand", op="not_in", value=["Samsung", "Apple"])
        assert check_brand_exclude(p, c) is True

    def test_excluded_brand_fails(self):
        p = _make_product(brand="Samsung")
        c = _make_constraint(kind="brand_exclude", key="brand", op="not_in", value=["Samsung", "Apple"])
        assert check_brand_exclude(p, c) is False

    def test_null_brand_unverifiable(self):
        p = _make_product(brand=None)
        c = _make_constraint(kind="brand_exclude", key="brand", op="not_in", value=["Samsung"])
        assert check_brand_exclude(p, c) is None

    def test_case_insensitive(self):
        p = _make_product(brand="samsung")
        c = _make_constraint(kind="brand_exclude", key="brand", op="not_in", value=["Samsung"])
        assert check_brand_exclude(p, c) is False


# ---------------------------------------------------------------------------
# must_have constraint
# ---------------------------------------------------------------------------

class TestMustHave:

    def _product_with_specs(self, spec_text: str) -> dict:
        return _make_product(specification_text=spec_text, specs_parsed=None)

    def test_must_have_noise_cancellation_present_and_true(self):
        p = _make_product(
            specs_parsed={"noise_cancellation": {"value": True, "unit": "", "spec_id": "spec:P001:1", "raw_value": "Yes"}}
        )
        c = _make_constraint(kind="must_have", key="noise_cancellation", op="eq", value=True)
        assert check_must_have(p, c) is True

    def test_must_have_noise_cancellation_false(self):
        p = _make_product(
            specs_parsed={"noise_cancellation": {"value": False, "unit": "", "spec_id": "spec:P001:1", "raw_value": "No"}}
        )
        c = _make_constraint(kind="must_have", key="noise_cancellation", op="eq", value=True)
        assert check_must_have(p, c) is False

    def test_must_have_key_absent_unverifiable(self):
        p = _make_product(specs_parsed={})
        c = _make_constraint(kind="must_have", key="hdmi_count", op="gte", value=1)
        assert check_must_have(p, c) is None

    def test_must_have_gte_passes(self):
        p = _make_product(
            specs_parsed={"ram_gb": {"value": 16.0, "unit": "GB", "spec_id": "spec:P001:1", "raw_value": "16GB"}}
        )
        c = _make_constraint(kind="must_have", key="ram_gb", op="gte", value=8)
        assert check_must_have(p, c) is True

    def test_must_have_gte_fails(self):
        p = _make_product(
            specs_parsed={"ram_gb": {"value": 4.0, "unit": "GB", "spec_id": "spec:P001:1", "raw_value": "4GB"}}
        )
        c = _make_constraint(kind="must_have", key="ram_gb", op="gte", value=8)
        assert check_must_have(p, c) is False


# ---------------------------------------------------------------------------
# weight_limit and size_limit
# ---------------------------------------------------------------------------

class TestWeightAndSize:

    def _p(self, specs_parsed: dict) -> dict:
        return _make_product(specs_parsed=specs_parsed)

    def test_weight_under_limit_passes(self):
        p = self._p({"weight_kg": {"value": 1.5, "unit": "kg", "spec_id": "s:1", "raw_value": "1.5 kg"}})
        c = _make_constraint(kind="weight_limit", key="weight_kg", op="lte", value=2.0)
        assert check_weight_limit(p, c) is True

    def test_weight_over_limit_fails(self):
        p = self._p({"weight_kg": {"value": 2.5, "unit": "kg", "spec_id": "s:1", "raw_value": "2.5 kg"}})
        c = _make_constraint(kind="weight_limit", key="weight_kg", op="lte", value=2.0)
        assert check_weight_limit(p, c) is False

    def test_weight_absent_unverifiable(self):
        p = self._p({})
        c = _make_constraint(kind="weight_limit", key="weight_kg", op="lte", value=2.0)
        assert check_weight_limit(p, c) is None

    def test_size_under_limit_passes(self):
        p = self._p({"screen_inch": {"value": 14.0, "unit": "inch", "spec_id": "s:1", "raw_value": "14 inch"}})
        c = _make_constraint(kind="size_limit", key="screen_inch", op="lte", value=15.6)
        assert check_size_limit(p, c) is True

    def test_size_over_limit_fails(self):
        p = self._p({"screen_inch": {"value": 17.3, "unit": "inch", "spec_id": "s:1", "raw_value": "17.3 inch"}})
        c = _make_constraint(kind="size_limit", key="screen_inch", op="lte", value=15.6)
        assert check_size_limit(p, c) is False


# ---------------------------------------------------------------------------
# Gate — property: no product that fails a hard constraint should pass
# ---------------------------------------------------------------------------

class TestGate:

    PRODUCTS = [
        _make_product(product_id="P001", effective_price_inr=45000, brand="HP",
                      cat_l2="Laptops",
                      specs_parsed={"weight_kg": {"value": 1.5, "unit": "kg", "spec_id": "s:1", "raw_value": "1.5kg"}}),
        _make_product(product_id="P002", effective_price_inr=55000, brand="Dell",
                      cat_l2="Laptops",
                      specs_parsed={"weight_kg": {"value": 2.2, "unit": "kg", "spec_id": "s:1", "raw_value": "2.2kg"}}),
        _make_product(product_id="P003", effective_price_inr=None, brand="Asus",
                      cat_l2="Laptops",
                      specs_parsed={}),
    ]

    def test_budget_gate_filters_over_budget(self):
        constraints = [_make_constraint(kind="budget", op="lte", value=50000)]
        passed = [p for p in self.PRODUCTS if gate(p, constraints, "exclude")[0]]
        ids = [p["product_id"] for p in passed]
        assert "P002" not in ids    # 55000 > 50000
        assert "P001" in ids        # 45000 <= 50000

    def test_property_no_gated_product_fails_constraint(self):
        """Property: for every product that passes gate(), all checked constraints are True."""
        constraints = [
            _make_constraint(kind="budget", op="lte", value=50000),
        ]
        for p in self.PRODUCTS:
            passes, _ = gate(p, constraints, unverifiable_policy="include")
            if passes and p["effective_price_inr"] is not None:
                assert p["effective_price_inr"] <= 50000, (
                    f"Gate passed P{p['product_id']} but price "
                    f"{p['effective_price_inr']} > 50000"
                )

    def test_unverifiable_exclude_policy_gates_out(self):
        """With policy='exclude', unverifiable (price_unknown) is gated out."""
        constraints = [_make_constraint(kind="budget", op="lte", value=50000)]
        p = _make_product(effective_price_inr=None)
        passes, reasons = gate(p, constraints, unverifiable_policy="exclude")
        assert not passes
        assert any("unverifiable" in r for r in reasons)

    def test_unverifiable_include_policy_passes(self):
        """With policy='include', unverifiable is not gated out."""
        constraints = [_make_constraint(kind="budget", op="lte", value=50000)]
        p = _make_product(effective_price_inr=None)
        passes, _ = gate(p, constraints, unverifiable_policy="include")
        assert passes

    def test_multiple_constraints_all_must_pass(self):
        """Product must pass ALL constraints — one failure is enough to gate out."""
        constraints = [
            _make_constraint(kind="budget", op="lte", value=50000),
            _make_constraint(kind="category", key="category", op="eq", value="Smartphones"),
        ]
        p = _make_product(effective_price_inr=45000, cat_l2="Laptops")
        passes, reasons = gate(p, constraints, "include")
        assert not passes   # category fails even though budget passes

    def test_empty_constraints_always_pass(self):
        passes, reasons = gate(_make_product(), [], "exclude")
        assert passes
        assert reasons == []


# ---------------------------------------------------------------------------
# SQL allow-list / filters.py
# ---------------------------------------------------------------------------

class TestAllowList:

    def _load_db(self) -> sqlite3.Connection:
        conn = _open_mem_db()
        products = [
            _make_product(product_id="P001", effective_price_inr=45000, brand="HP", cat_l2="Laptops", cat_l3="Gaming Laptop"),
            _make_product(product_id="P002", effective_price_inr=80000, brand="Dell", cat_l2="Laptops", cat_l3="Business Laptop"),
            _make_product(product_id="P003", effective_price_inr=25000, brand="Samsung", cat_l2="Smartphones", cat_l3="Budget Smartphone"),
            _make_product(product_id="P004", effective_price_inr=None, brand="Apple", cat_l2="Tablets", cat_l3="Premium Tablet"),
        ]
        insert_products(conn, products)
        return conn

    def test_budget_sql_filter(self):
        conn = self._load_db()
        constraints = [_make_constraint(kind="budget", op="lte", value=50000)]
        allow, residual = build_allow_list(conn, constraints)
        assert "P001" in allow   # 45k
        assert "P002" not in allow  # 80k
        assert "P003" in allow   # 25k
        assert "P004" not in allow  # price NULL

    def test_category_sql_filter(self):
        conn = self._load_db()
        constraints = [_make_constraint(kind="category", key="category", op="eq", value="Laptops")]
        allow, residual = build_allow_list(conn, constraints)
        assert "P001" in allow
        assert "P002" in allow
        assert "P003" not in allow

    def test_brand_exclude_sql_filter(self):
        conn = self._load_db()
        constraints = [_make_constraint(kind="brand_exclude", key="brand", op="not_in", value=["Samsung", "Apple"])]
        allow, residual = build_allow_list(conn, constraints)
        assert "P001" in allow
        assert "P002" in allow
        assert "P003" not in allow

    def test_must_have_goes_to_residual(self):
        conn = self._load_db()
        constraints = [_make_constraint(kind="must_have", key="hdmi_count", op="gte", value=1)]
        allow, residual = build_allow_list(conn, constraints)
        assert len(residual) == 1
        assert residual[0].kind == "must_have"
        # All canonical products in allow (no SQL filter applied)
        assert len(allow) == 4

    def test_combined_budget_and_category(self):
        conn = self._load_db()
        constraints = [
            _make_constraint(kind="budget", op="lte", value=50000),
            _make_constraint(kind="category", key="category", op="eq", value="Laptops"),
        ]
        allow, _ = build_allow_list(conn, constraints)
        assert "P001" in allow   # 45k + Laptops ✓
        assert "P002" not in allow  # 80k ✗
        assert "P003" not in allow  # Smartphones ✗
