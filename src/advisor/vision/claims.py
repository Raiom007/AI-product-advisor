"""Deterministic claim extraction for vision (§5.5)."""
import re
from typing import Dict, List, Any

# Keywords that suggest a visual claim
VISUAL_PATTERNS = [
    (r"\b(?:hdmi|usb|type-c|thunderbolt|ethernet|rj45|audio jack|ports?)\b", "ports"),
    (r"\b(?:numeric keypad|numpad)\b", "numeric keypad"),
    (r"\b(?:bezel|bezels)\b", "bezel"),
    (r"\b(?:included|in the box|accessories|charger|cable)\b", "included accessories"),
]

def extract_claims(evidence_pool: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Extract checkable claims from spec lines and reviews.
    
    evidence_pool: list of dicts like {"id": "spec:P1:4", "text": "...", "kind": "spec_line"}
    Returns list of dicts: {"claim": "has numeric keypad", "source_ref": "spec:P1:4"}
    """
    claims = []
    seen = set()
    
    for item in evidence_pool:
        text = item.get("text", "").lower()
        source_id = item.get("id")
        
        for pattern, claim_type in VISUAL_PATTERNS:
            if re.search(pattern, text):
                claim_text = f"Check if {claim_type} is present/visible"
                key = (claim_text, source_id)
                if key not in seen:
                    claims.append({
                        "claim": claim_text,
                        "source_ref": source_id,
                        "raw_text": item.get("text", "")
                    })
                    seen.add(key)
                    
    return claims
