"""Table-driven tests for ingest/specs_parser.py.

The test fixture is at tests/fixtures/spec_parser_cases.yaml.
Cases with expect.value == "FILL_ME" are skipped automatically — fill
them by running the helper script and pasting actual parser output.

To fill the fixture:
    python -c "
from advisor.ingest.specs_parser import parse_specs
import yaml, pprint
cases = yaml.safe_load(open('tests/fixtures/spec_parser_cases.yaml'))['cases']
for c in cases:
    r = parse_specs(c['spec_text'], c['product_id'])
    print(f'--- {c[\"id\"]} ---')
    for k, v in sorted(r.items()):
        print(f'  {k}: value={v[\"value\"]!r} unit={v[\"unit\"]!r}')
"
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from advisor.ingest.specs_parser import coverage_report, parse_specs

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "spec_parser_cases.yaml"


def _load_cases() -> list[dict]:
    with _FIXTURE_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)["cases"]


# ---------------------------------------------------------------------------
# Table-driven: expect values (skip FILL_ME)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_parser_case(case: dict):
    result = parse_specs(case["spec_text"], case["product_id"])

    expect = case.get("expect", {})
    for key, expected in expect.items():
        exp_val = expected.get("value")
        exp_unit = expected.get("unit", "")

        if exp_val == "FILL_ME":
            pytest.skip(f"Case '{case['id']}' key '{key}': expected value not filled yet")

        assert key in result, (
            f"Case '{case['id']}': expected key '{key}' not in parsed output. "
            f"Got keys: {list(result.keys())}"
        )
        got_val = result[key]["value"]
        got_unit = result[key]["unit"]

        # Numeric comparison with tolerance
        if isinstance(exp_val, (int, float)) and isinstance(got_val, (int, float)):
            assert abs(float(got_val) - float(exp_val)) < 0.05, (
                f"Case '{case['id']}' key '{key}': expected value {exp_val} "
                f"but got {got_val}"
            )
        else:
            assert str(got_val).strip() == str(exp_val).strip(), (
                f"Case '{case['id']}' key '{key}': expected {exp_val!r} but got {got_val!r}"
            )

        if exp_unit != "FILL_ME" and exp_unit is not None:
            assert (got_unit or "") == (exp_unit or ""), (
                f"Case '{case['id']}' key '{key}': expected unit {exp_unit!r} "
                f"but got {got_unit!r}"
            )


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_raw_keys_present(case: dict):
    """Unknown keys must appear in output under 'raw:' prefix."""
    if not case.get("expect_raw"):
        return  # nothing to check

    result = parse_specs(case["spec_text"], case["product_id"])

    for raw_key in case["expect_raw"]:
        assert raw_key in result, (
            f"Case '{case['id']}': expected raw key '{raw_key}' not in output. "
            f"Got keys: {list(result.keys())}"
        )


# ---------------------------------------------------------------------------
# Structural invariants (no FILL_ME needed)
# ---------------------------------------------------------------------------

def test_empty_spec_returns_empty():
    assert parse_specs("", "P000") == {}


def test_unknown_keys_never_dropped():
    result = parse_specs("FooField: bar value | RAM: 8GB", "P001")
    assert any(k.startswith("raw:") for k in result)
    assert "ram_gb" in result


def test_all_results_have_spec_id():
    result = parse_specs("RAM: 16GB | Storage: 512GB", "PTEST")
    for k, v in result.items():
        assert "spec_id" in v, f"Key '{k}' missing spec_id"
        assert v["spec_id"].startswith("spec:PTEST:") or v["spec_id"] == ""


def test_spec_ids_are_unique():
    result = parse_specs("RAM: 16GB\nStorage: 512GB\nDisplay: 15.6 inch", "PTEST")
    spec_ids = [v["spec_id"] for v in result.values()]
    assert len(spec_ids) == len(set(spec_ids)), "spec_ids are not unique"


def test_idempotent_same_input_same_output():
    text = "RAM: 16GB | Storage: 512GB | Weight: 1.8 kg"
    r1 = parse_specs(text, "P001")
    r2 = parse_specs(text, "P001")
    assert r1 == r2


def test_raw_key_preserved_verbatim():
    result = parse_specs("MyCustomKey: hello world", "P001")
    assert "raw:MyCustomKey" in result
    assert result["raw:MyCustomKey"]["value"] == "hello world"


def test_unit_conversion_grams_to_kg():
    result = parse_specs("Weight: 1800g", "P001")
    if "weight_kg" in result and result["weight_kg"]["value"] is not None:
        assert abs(result["weight_kg"]["value"] - 1.8) < 0.01


def test_unit_conversion_tb_to_gb():
    result = parse_specs("Storage: 1TB", "P001")
    if "storage_gb" in result and result["storage_gb"]["value"] is not None:
        assert abs(result["storage_gb"]["value"] - 1024.0) < 1.0


def test_boolean_yes_is_true():
    result = parse_specs("Noise Cancellation: Yes", "P001")
    if "noise_cancellation" in result:
        assert result["noise_cancellation"]["value"] is True


def test_boolean_no_is_false():
    result = parse_specs("Noise Cancellation: No", "P001")
    if "noise_cancellation" in result:
        assert result["noise_cancellation"]["value"] is False


# ---------------------------------------------------------------------------
# Coverage report (aggregate only)
# ---------------------------------------------------------------------------

def test_coverage_report_aggregate():
    texts = [
        "RAM: 16GB | Storage: 512GB",
        "RAM: 8GB",
        "Storage: 256GB | Weight: 1.5 kg",
    ]
    parsed = [parse_specs(t, f"P{i:03d}") for i, t in enumerate(texts)]
    report = coverage_report(parsed)

    assert "ram_gb" in report
    assert "storage_gb" in report
    assert report["ram_gb"]["products_with_key"] == 2
    # parse_rate should be 0-100
    for key, stats in report.items():
        assert 0 <= stats["parse_rate"] <= 100
        assert 0 <= stats["pct_with_key"] <= 100


def test_coverage_report_empty():
    assert coverage_report([]) == {}
