"""Explanation: composer, grounding_validator, render (§5.7)."""
from advisor.explain.composer import ComposerResponse, compose
from advisor.explain.grounding_validator import validate_composition
from advisor.explain.render import (
    make_abstention_response,
    render_recommendation,
    template_recommendation,
)
