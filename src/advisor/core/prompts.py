"""Versioned prompt template loader.

Loads prompt templates from prompts/*.md and returns the raw text plus a
SHA-256 fingerprint.

WHY: The fingerprint lets the gateway detect stale cache entries when a
     prompt template changes — it should be included in the cache key
     alongside model, role, schema, and params (§5.9, P9 gateway).
     Prompts live in versioned .md files (not in Python strings) so they
     can be reviewed, diffed, and updated without touching code (§1 rule 7).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import NamedTuple

# WHY: resolve() handles symlinks; parent×4 walks src/advisor/core/ → project root.
_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"


class PromptTemplate(NamedTuple):
    name: str
    text: str
    sha256: str


def load_prompt(name: str, prompts_dir: Path | None = None) -> PromptTemplate:
    """Load a prompt template by name (without .md extension).

    Args:
        name:        template name, e.g. "parser", "composer".
        prompts_dir: override default prompts/ directory (used in tests).

    Raises:
        FileNotFoundError: if prompts/{name}.md does not exist.
    """
    root = prompts_dir or _PROMPTS_DIR
    path = root / f"{name}.md"
    text = path.read_text(encoding="utf-8")  # raises FileNotFoundError if missing
    digest = hashlib.sha256(text.encode()).hexdigest()
    return PromptTemplate(name=name, text=text, sha256=digest)


def list_prompts(prompts_dir: Path | None = None) -> list[str]:
    """Return names of all .md files in the prompts directory."""
    root = prompts_dir or _PROMPTS_DIR
    if not root.exists():
        return []
    return [p.stem for p in sorted(root.glob("*.md"))]
