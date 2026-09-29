"""Extension-point tests — from OUTSIDE core/, register dummy plug-ins and
prove each is discoverable via enabled() with zero edits to core/.

This test intentionally imports only from advisor.core.registries (the public
surface) and never touches the internals of Registry[T].

It will be extended in P15 (agent executor) and P16 (scorer) to run the
dummy plug-ins through the real executor and scorer pipelines.
"""
from __future__ import annotations

import pytest

from advisor.core.registries import (
    constraint_kinds,
    evidence_kinds,
    fake_signals,
    guardrails,
    ranking_signals,
    tools,
    validate_constraint_kind,
    validate_evidence_kind,
    verifiers,
    providers,
    retrievers,
    eval_suites,
    # decorator shortcuts
    tool,
    ranking_signal,
    fake_signal,
    guardrail,
    constraint_kind,
    evidence_kind,
    retriever,
    provider,
    suite,
    verifier,
)
from advisor.core.schemas import ScoreBreakdown


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_enabled(registry) -> list[str]:
    """Return all names enabled with an empty features dict (permissive default)."""
    return registry.list_enabled({})


# ---------------------------------------------------------------------------
# Tool registration from outside core/
# ---------------------------------------------------------------------------

def test_register_dummy_tool_discoverable():
    """Register a dummy tool and confirm it appears in list_enabled."""

    @tool("_test_dummy_tool")
    def dummy_tool(state):
        return "dummy"

    assert "_test_dummy_tool" in _all_enabled(tools)
    assert tools.get("_test_dummy_tool")(None) == "dummy"


# ---------------------------------------------------------------------------
# Ranking signal registration from outside core/
# ---------------------------------------------------------------------------

def test_register_dummy_ranking_signal_discoverable():
    """Register a dummy ranking signal and confirm it appears in list_enabled."""

    @ranking_signal("_test_price_competitiveness")
    def price_competitiveness_signal(product, context):
        # WHY: Returns 0.42 so we can confirm it appears in ScoreBreakdown.ext
        return 0.42

    assert "_test_price_competitiveness" in _all_enabled(ranking_signals)
    signal_fn = ranking_signals.get("_test_price_competitiveness")
    value = signal_fn(None, None)
    assert value == 0.42


def test_dummy_ranking_signal_value_in_score_breakdown():
    """Show a ScoreBreakdown carrying a dummy signal's output in ext."""

    # Run the dummy signal registered above (or re-register if tests are isolated)
    if "_test_price_competitiveness" not in ranking_signals.all_names():
        @ranking_signal("_test_price_comp_v2")
        def _sig(product, context):
            return 0.42
        signal_name = "_test_price_comp_v2"
    else:
        signal_name = "_test_price_competitiveness"

    fn = ranking_signals.get(signal_name)
    dummy_value = fn(None, None)

    score = ScoreBreakdown(
        relevance=0.8, soft_fit=0.7, use_case_sentiment=0.6,
        review_trust=0.9, visual=None, total=0.74,
        weights_used={"relevance": 0.30, "soft_fit": 0.15,
                      "use_case_sentiment": 0.30, "review_trust": 0.25},
        ext={signal_name: dummy_value},
    )

    assert score.ext[signal_name] == 0.42
    assert score.visual is None  # vision skipped path


# ---------------------------------------------------------------------------
# Fake signal registration from outside core/
# ---------------------------------------------------------------------------

def test_register_dummy_fake_signal_discoverable():
    """Register a dummy fake-review signal and confirm discoverability."""

    @fake_signal("_test_template_burst")
    def template_burst(review, context):
        return 0.9

    assert "_test_template_burst" in _all_enabled(fake_signals)
    fn = fake_signals.get("_test_template_burst")
    assert fn(None, None) == 0.9


# ---------------------------------------------------------------------------
# Guardrail registration from outside core/
# ---------------------------------------------------------------------------

def test_register_dummy_guardrail_discoverable():
    """Register a dummy pre-stage guardrail and confirm discoverability."""

    @guardrail(stage="pre")("_test_length_check")
    def length_check(text):
        return len(text) < 10000

    assert "_test_length_check" in _all_enabled(guardrails)
    fn = guardrails.get("_test_length_check")
    assert fn("short text") is True


def test_guardrail_stage_attribute_stored():
    """Confirm the stage attribute is stored on the registered function."""
    fn = guardrails.get("_test_length_check")
    assert fn._guardrail_stage == "pre"


# ---------------------------------------------------------------------------
# Verifier registration
# ---------------------------------------------------------------------------

def test_register_dummy_verifier_discoverable():

    @verifier("_test_parse_sane")
    def parse_sane(result):
        return result is not None

    assert "_test_parse_sane" in _all_enabled(verifiers)


# ---------------------------------------------------------------------------
# Feature-flag gating (enabled() with features dict)
# ---------------------------------------------------------------------------

def test_dummy_tool_disabled_by_features():
    features = {"tools": {"_test_dummy_tool": False}}
    assert not tools.enabled("_test_dummy_tool", features)


def test_dummy_ranking_signal_disabled_by_features():
    features = {"ranking_signals": {"_test_price_competitiveness": False}}
    assert not ranking_signals.enabled("_test_price_competitiveness", features)


def test_dummy_fake_signal_enabled_when_not_in_features():
    # Permissive default: missing from features dict → True
    features = {"ranking_signals": {}}  # wrong registry key
    assert fake_signals.enabled("_test_template_burst", features) is True


# ---------------------------------------------------------------------------
# Built-in constraint and evidence kinds
# ---------------------------------------------------------------------------

def test_built_in_constraint_kinds_registered():
    for kind in ("category", "brand_exclude", "must_have",
                 "size_limit", "weight_limit", "budget"):
        assert kind in constraint_kinds.all_names()


def test_built_in_evidence_kinds_registered():
    for kind in ("spec_line", "review", "image_obs"):
        assert kind in evidence_kinds.all_names()


# ---------------------------------------------------------------------------
# Runtime validation: unknown kinds rejected
# ---------------------------------------------------------------------------

def test_validate_constraint_kind_known_passes():
    validate_constraint_kind("budget")   # must not raise


def test_validate_constraint_kind_unknown_raises():
    with pytest.raises(ValueError, match="Unknown Constraint.kind"):
        validate_constraint_kind("totally_unknown_xyz")


def test_validate_evidence_kind_known_passes():
    validate_evidence_kind("spec_line")  # must not raise


def test_validate_evidence_kind_unknown_raises():
    with pytest.raises(ValueError, match="Unknown EvidenceRef.kind"):
        validate_evidence_kind("totally_unknown_xyz")


# ---------------------------------------------------------------------------
# Plug-in constraint and evidence kinds extend the registry
# ---------------------------------------------------------------------------

def test_register_plugin_constraint_kind_then_valid():
    @constraint_kind("_test_delivery_speed")
    def delivery_speed_handler(**kwargs): pass

    assert "_test_delivery_speed" in constraint_kinds.all_names()
    validate_constraint_kind("_test_delivery_speed")  # must not raise now


def test_register_plugin_evidence_kind_then_valid():
    @evidence_kind("_test_price_history")
    def price_history_handler(**kwargs): pass

    assert "_test_price_history" in evidence_kinds.all_names()
    validate_evidence_kind("_test_price_history")  # must not raise now


# ---------------------------------------------------------------------------
# Other registries: retriever, provider, suite
# ---------------------------------------------------------------------------

def test_register_dummy_retriever():
    @retriever("_test_hybrid_v2")
    def hybrid_v2(query, allow_ids, k): pass

    assert "_test_hybrid_v2" in retrievers.all_names()


def test_register_dummy_provider():
    @provider("_test_mock_llm")
    def mock_llm(role, prompt, schema, params): pass

    assert "_test_mock_llm" in providers.all_names()


def test_register_dummy_suite():
    @suite("_test_smoke")
    def smoke_suite(): pass

    assert "_test_smoke" in eval_suites.all_names()
