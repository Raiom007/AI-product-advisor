"""Vision verifier (§5.5)."""

from pydantic import BaseModel

from advisor.core.schemas import VisualCheck


class NewObservation(BaseModel):
    text: str
    image_ids: list[str]

class VisionResponse(BaseModel):
    checks: list[VisualCheck]
    new_observations: list[NewObservation]
