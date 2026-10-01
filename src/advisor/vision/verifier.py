"""Vision verifier: one multi-image call per product (§5.5)."""
from __future__ import annotations

import base64
import logging
from typing import Any

from advisor.core.schemas import VisualCheck, EvidenceRef
from advisor.core.config import load_config
from advisor.llm.gateway import Gateway
from advisor.core.budget import RequestBudget
from advisor.guardrails.untrusted import spotlight_system_rule
from advisor.vision.fetch import fetch_image
from advisor.vision.claims import extract_claims
from advisor.vision.schemas import VisionResponse

logger = logging.getLogger(__name__)


def verify_product_images(
    product: dict,
    evidence_pool: list[dict],
    gateway: Gateway,
    budget: RequestBudget,
) -> tuple[list[VisualCheck], list[EvidenceRef], str]:
    """Run vision verification on a single product.

    Returns (visual_checks, new_obs_evidence, skip_reason).
    If skip_reason is non-empty, vision was skipped — caller must degrade.
    """
    config = load_config()
    thresholds = config.get("ranking", {}).get("thresholds", {})
    images_per_product: int = thresholds.get("images_per_product", 3)

    # 1. Deterministic claim extraction from evidence pool
    claims = extract_claims(evidence_pool)

    # 2. Fetch images
    image_urls: list[str] = product.get("image_urls", [])[:images_per_product]
    images_b64: list[dict[str, str]] = []  # [{url, b64, img_id}]
    for i, url in enumerate(image_urls):
        raw = fetch_image(url)
        if raw is None:
            logger.info(f"Product {product.get('id')}: image {url} skipped (fetch failed)")
            continue
        b64 = base64.b64encode(raw).decode()
        images_b64.append({"url": url, "b64": b64, "img_id": f"img:{product.get('id')}:{i}"})

    if not images_b64:
        return [], [], "no images available"

    if not claims:
        # Still run to extract new observations, but with an empty claims list
        pass

    # 3. Build prompt
    claim_lines = "\n".join(
        f"- [{c['source_ref']}] {c['claim']}" for c in claims
    ) or "No textual claims to verify. Look for notable features."

    prompt = (
        "You are examining product images.\n"
        f"Image IDs provided: {', '.join(i['img_id'] for i in images_b64)}\n\n"
        f"Claims to verify (source_ref in brackets):\n{claim_lines}\n\n"
        "For each claim, respond with 'agree', 'disagree', or 'unverifiable'.\n"
        "Also list any notable features you observe that are NOT mentioned in the claims above "
        "(e.g. box accessories, ports not listed) as new_observations.\n"
        "Return structured JSON only."
    )
    system = spotlight_system_rule()

    # 4. Call vision gateway
    # WHY: images are passed as b64 blobs; gateway.call() already has the vision role wired.
    try:
        resp = gateway.call(
            role="vision",
            prompt=prompt,
            system=system,
            schema=VisionResponse,
            budget=budget,
            # Extra: pass images as context (gateway-specific handling)
            images=[{"data": img["b64"], "id": img["img_id"]} for img in images_b64],
        )
    except Exception as e:
        return [], [], f"gateway error: {e}"

    if not resp or not resp.structured_data:
        return [], [], "malformed vision response"

    vision_resp: VisionResponse = resp.structured_data

    # 5. Validate VisualCheck fields
    checks: list[VisualCheck] = []
    valid_img_ids = {img["img_id"] for img in images_b64}
    valid_source_refs = {c["source_ref"] for c in claims}

    for vc in vision_resp.checks:
        # Reject hallucinated source refs
        if vc.source_ref and vc.source_ref not in valid_source_refs:
            logger.warning(
                f"Vision check has hallucinated source_ref '{vc.source_ref}' — dropped"
            )
            continue
        checks.append(vc)

    # 6. Convert new observations into EvidenceRef items
    new_obs: list[EvidenceRef] = []
    for i, obs in enumerate(vision_resp.new_observations):
        obs_id = f"img:{product.get('id')}:obs:{i}"
        new_obs.append(
            EvidenceRef(
                id=obs_id,
                kind="image_obs",
                product_id=str(product.get("id", "")),
                text=obs.text,
                meta={"image_ids": obs.image_ids},
            )
        )

    return checks, new_obs, ""


def run_vision_for_shortlist(
    shortlist: list[dict],
    evidence_map: dict[str, list[dict]],
    gateway: Gateway,
    budget: RequestBudget,
    degraded: list[str],
    top_n: int | None = None,
) -> None:
    """Run vision verification on top-N products, mutating each product dict in place."""
    config = load_config()
    thresholds = config.get("ranking", {}).get("thresholds", {})
    top_n = top_n or thresholds.get("vision_top_n", 3)

    for product in shortlist[:top_n]:
        pid = str(product.get("id", ""))
        evidence = evidence_map.get(pid, [])

        checks, new_obs, skip_reason = verify_product_images(
            product, evidence, gateway, budget
        )

        if skip_reason:
            product["vision_skipped"] = True
            product["vision_skip_reason"] = skip_reason
            degraded.append(f"vision_skipped:{pid}:{skip_reason}")
            logger.info(f"Vision skipped for {pid}: {skip_reason}")
        else:
            product["visual_checks"] = [c.model_dump() for c in checks]
            product["image_obs_evidence"] = [e.model_dump() for e in new_obs]
            # Mark contradiction
            product["has_contradiction"] = any(
                c.get("verdict") == "disagree" for c in product["visual_checks"]
            )
