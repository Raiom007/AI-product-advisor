"""Vision verifier (§5.5)."""
from pydantic import BaseModel
from typing import List, Optional
from advisor.core.schemas import VisualCheck

class NewObservation(BaseModel):
    text: str
    image_ids: List[str]

class VisionResponse(BaseModel):
    checks: List[VisualCheck]
    new_observations: List[NewObservation]
