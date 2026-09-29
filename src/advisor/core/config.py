"""Configuration loader: YAML base files + profile overlay + env resolution.

Design:
- Base config = merge of all configs/*.yaml files (keys = filenames without .yaml).
- Active profile = $ADVISOR_PROFILE (default: "dev"); its YAML is deep-merged on top.
- Secrets (GEMINI_API_KEY, GROQ_API_KEY) are NOT merged into the config dict —
  callers read them from os.environ directly so they never appear in traces or logs.
- Config hash (SHA-256 of the serialised dict) is stamped on every RunManifest and
  eval report so "same numbers" can be verified (§5.9, §13 DoD bullet 3).

WHY: All model IDs, weights, thresholds and budgets live in configs/, never in code
     (ARCHITECTURE.md §1 rule 7, AGENTS.md rule 4).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml

# WHY: resolve() handles symlinks; parent×4 walks src/advisor/core/ → project root.
_CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "configs"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into base; overlay values win on conflict."""
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(configs_dir: Path | None = None) -> dict[str, Any]:
    """Load all YAML files in configs/ and apply the active profile overlay.

    Args:
        configs_dir: override the default configs/ directory (used in tests).

    Returns:
        Merged config dict with two extra keys:
          _profile: the active profile name
          _hash:    SHA-256 of the config dict (stable across reloads)
    """
    root = configs_dir or _CONFIGS_DIR
    config: dict[str, Any] = {}

    # Load every *.yaml in the root (sorted for determinism)
    for yaml_file in sorted(root.glob("*.yaml")):
        config[yaml_file.stem] = _load_yaml(yaml_file)

    # Apply profile overlay
    profile = os.environ.get("ADVISOR_PROFILE", "dev")
    profile_path = root / "profiles" / f"{profile}.yaml"
    if profile_path.exists():
        overlay = _load_yaml(profile_path)
        config = _deep_merge(config, overlay)

    config["_profile"] = profile
    config["_hash"] = config_hash(config)
    return config


def config_hash(config: dict[str, Any]) -> str:
    """Stable SHA-256 of the config dict (excludes the _hash key itself).

    WHY: Sort keys so Python dict insertion order doesn't affect the hash.
         Used by RunManifest and eval replay to verify identical settings.
    """
    payload = {k: v for k, v in config.items() if k != "_hash"}
    serialised = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode()).hexdigest()
