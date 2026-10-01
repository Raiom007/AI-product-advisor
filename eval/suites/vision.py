"""Vision eval suite — agreement % against eval/data/image_claims.jsonl (§8)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from advisor.core.registries import suite

CLAIMS_PATH = Path(__file__).resolve().parent.parent / "data" / "image_claims.jsonl"


def load_labelled_claims() -> list[dict[str, Any]]:
    """Load claims that have been labelled (truth != null)."""
    if not CLAIMS_PATH.exists():
        return []
    claims = []
    with CLAIMS_PATH.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("truth") is not None:
                claims.append(item)
    return claims


def show_claim_for_labelling(claim: dict[str, Any]) -> None:
    """Print a claim to stdout so the owner can open the image and mark truth.

    Usage: run `python -m eval.suites.vision --label` to iterate unlabelled claims.
    The owner edits image_claims.jsonl and sets truth = "agree"/"disagree"/"unverifiable".
    """
    print(f"\n{'='*60}")
    print(f"product_id : {claim['product_id']}")
    print(f"image_url  : {claim['image_url']}")
    print(f"claim      : {claim['claim']}")
    print(f"truth      : {claim.get('truth', '<unlabelled>')}")
    print(f"{'='*60}")


@suite("vision")
def run_vision_eval(gateway=None, budget=None) -> dict[str, Any]:
    """Run vision eval: compare model verdicts against labelled truths.

    Returns dict with agreement_pct and per-claim results.
    """
    from advisor.vision.verifier import verify_product_images
    from advisor.core.budget import RequestBudget

    labelled = load_labelled_claims()
    if not labelled:
        return {
            "status": "no_labelled_claims",
            "message": "Run `python -m eval.suites.vision --label` to mark truths first.",
            "agreement_pct": None,
        }

    budget = budget or RequestBudget()
    results = []

    for item in labelled:
        product = {"id": item["product_id"], "image_urls": [item["image_url"]]}
        # Build a minimal evidence pool so claims.py fires
        evidence_pool = [
            {"id": f"spec:{item['product_id']}:0", "text": item["claim"], "kind": "spec_line"}
        ]
        checks, _, skip = verify_product_images(product, evidence_pool, gateway, budget)
        if skip:
            results.append(
                {"claim": item["claim"], "product_id": item["product_id"],
                 "truth": item["truth"], "model_verdict": "skipped", "match": False}
            )
            continue

        model_verdict = None
        for c in checks:
            if c.claim == item["claim"]:
                model_verdict = c.verdict
                break

        match = model_verdict == item["truth"]
        results.append(
            {"claim": item["claim"], "product_id": item["product_id"],
             "truth": item["truth"], "model_verdict": model_verdict, "match": match}
        )

    if not results:
        return {"agreement_pct": 0.0, "results": []}

    agreement_pct = 100.0 * sum(r["match"] for r in results) / len(results)
    return {"agreement_pct": round(agreement_pct, 1), "n": len(results), "results": results}


if __name__ == "__main__":
    import sys

    if "--label" in sys.argv:
        # Interactive labelling helper
        if not CLAIMS_PATH.exists():
            print("No image_claims.jsonl found.")
            sys.exit(1)

        with CLAIMS_PATH.open() as f:
            claims = [json.loads(l) for l in f if l.strip()]

        unlabelled = [c for c in claims if c.get("truth") is None]
        print(f"{len(unlabelled)} unlabelled claims out of {len(claims)} total.")
        for c in unlabelled:
            show_claim_for_labelling(c)
    else:
        result = run_vision_eval()
        print(json.dumps(result, indent=2))
