
from pydantic import BaseModel


class LLMCapabilities(BaseModel):
    """Capabilities supported by an LLM provider/model."""
    structured_output: bool = False
    vision: bool = False
    max_context_window: int = 8192
    supports_system_prompt: bool = True
