"""Tests for vision (§5.5): fetch, claims, verifier, degrade, contradiction."""
from __future__ import annotations

import io
import pytest
from unittest.mock import patch, MagicMock

from advisor.vision.claims import extract_claims
from advisor.vision.verifier import verify_product_images, run_vision_for_shortlist
from advisor.core.schemas import VisualCheck
from advisor.core.budget import RequestBudget
from advisor.vision.schemas import VisionResponse


# ── helpers ─────────────────────────────────────────────────────────────────

def _mock_gateway(checks: list[dict] | None = None, fail: bool = False):
    gw = MagicMock()
    if fail:
        gw.call.side_effect = RuntimeError("provider unavailable")
        return gw

    if checks is None:
        # Return malformed: no structured_data
        resp = MagicMock()
        resp.structured_data = None
        gw.call.return_value = resp
        return gw

    from advisor.llm.base import ProviderResponse
    obs = []
    resp = ProviderResponse(
        text="{}",
        tokens_in=1,
        tokens_out=1,
        structured_data=VisionResponse(
            checks=[VisualCheck(**c) for c in checks],
            new_observations=obs,
        ),
    )
    gw.call.return_value = resp
    return gw


def _fake_image_bytes() -> bytes:
    """1×1 white PNG."""
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )


# ── claim extraction ─────────────────────────────────────────────────────────

def test_claims_from_spec_lines():
    pool = [
        {"id": "spec:P1:0", "text": "Includes HDMI and 2x USB ports", "kind": "spec_line"},
        {"id": "spec:P1:1", "text": "Full-size numeric keypad on right side", "kind": "spec_line"},
        {"id": "spec:P1:2", "text": "15.6-inch FHD display", "kind": "spec_line"},  # no visual claim
    ]
    claims = extract_claims(pool)
    claim_texts = {c["claim"] for c in claims}

    assert any("ports" in t for t in claim_texts), "should find ports claim"
    assert any("numeric keypad" in t for t in claim_texts), "should find keypad claim"
    # No spec for display bezel text — should not hallucinate
    assert len(claims) >= 2


# ── fetch: broken URL ────────────────────────────────────────────────────────

def test_fetch_broken_url():
    from advisor.vision.fetch import fetch_image
    # Should return None, not raise
    result = fetch_image("http://localhost:19999/nonexistent.jpg")  # nothing listening
    assert result is None


def test_fetch_oversize_image():
    from advisor.vision.fetch import fetch_image, MAX_SIZE_BYTES
    big_payload = b"x" * (MAX_SIZE_BYTES + 1)

    with patch("httpx.Client") as MockClient:
        ctx = MockClient.return_value.__enter__.return_value
        stream_ctx = ctx.stream.return_value.__enter__.return_value
        stream_ctx.headers = {"content-type": "image/jpeg"}
        stream_ctx.raise_for_status = MagicMock()
        # Simulate streaming chunks that exceed the limit
        stream_ctx.iter_bytes.return_value = iter([big_payload])
        result = fetch_image("http://example.com/huge.jpg")

    assert result is None


# ── verifier: malformed output degrades ─────────────────────────────────────

def test_malformed_vision_output_degrades():
    """No structured_data → skip_reason is returned, not an exception."""
    gw = _mock_gateway(checks=None)  # returns structured_data=None
    product = {"id": "P1", "image_urls": ["http://example.com/img.jpg"]}
    evidence = [{"id": "spec:P1:0", "text": "Has USB ports", "kind": "spec_line"}]
    budget = RequestBudget()

    with patch("advisor.vision.fetch.fetch_image", return_value=_fake_image_bytes()):
        checks, new_obs, skip = verify_product_images(product, evidence, gw, budget)

    assert skip != ""  # must have a reason
    assert checks == []


def test_gateway_failure_degrades():
    """Gateway exception → skip_reason, not a crash."""
    gw = _mock_gateway(fail=True)
    product = {"id": "P1", "image_urls": ["http://example.com/img.jpg"]}
    evidence = [{"id": "spec:P1:0", "text": "Has HDMI port", "kind": "spec_line"}]
    budget = RequestBudget()

    with patch("advisor.vision.fetch.fetch_image", return_value=_fake_image_bytes()):
        checks, new_obs, skip = verify_product_images(product, evidence, gw, budget)

    assert skip != ""
    assert checks == []


# ── disagreement lowers confidence ──────────────────────────────────────────

def test_disagreement_lowers_confidence():
    from advisor.ranking.explain_rank import determine_confidence

    p_contradicted = {
        "id": "P1",
        "final_score": 0.9,
        "has_contradiction": True,
        "n_reviews_used": 5,
    }
    p2 = {"id": "P2", "final_score": 0.7, "has_contradiction": False, "n_reviews_used": 5}

    # Even with a large margin, contradiction forces low confidence
    conf = determine_confidence([p_contradicted, p2], context={"degraded": []})
    assert conf == "low"


def test_no_disagreement_allows_high_confidence():
    from advisor.ranking.explain_rank import determine_confidence

    p1 = {"id": "P1", "final_score": 0.9, "has_contradiction": False, "n_reviews_used": 5}
    p2 = {"id": "P2", "final_score": 0.7, "has_contradiction": False, "n_reviews_used": 5}

    conf = determine_confidence([p1, p2], context={"degraded": []})
    assert conf == "high"  # margin 0.2 > 0.15, >=3 reviews, no contradiction, no degraded
