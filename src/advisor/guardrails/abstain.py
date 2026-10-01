"""Abstention guardrails.

Register hooks at various stages to block execution if certain criteria are met.
WHY: §5.7 — Abstention when input or output violates policies.
"""
from advisor.core.registries import guardrail
from advisor.core.schemas import GuardResult


@guardrail(stage="input")("abstain_input")
def abstain_input(text: str) -> GuardResult:
    # Example block logic
    return GuardResult(guardrail="abstain_input", stage="input", action="pass")

@guardrail(stage="retrieved")("abstain_retrieved")
def abstain_retrieved(text: str) -> GuardResult:
    return GuardResult(guardrail="abstain_retrieved", stage="retrieved", action="pass")

@guardrail(stage="prompt")("abstain_prompt")
def abstain_prompt(text: str) -> GuardResult:
    return GuardResult(guardrail="abstain_prompt", stage="prompt", action="pass")

@guardrail(stage="output")("abstain_output")
def abstain_output(text: str) -> GuardResult:
    return GuardResult(guardrail="abstain_output", stage="output", action="pass")
