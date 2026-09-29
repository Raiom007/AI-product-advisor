"""Generic disk cache keyed by an arbitrary hash string.

WHY: Saves LLM quota during development and makes eval replayable (§5.9).
     Temperature 0 guarantees same inputs → same output → safe to cache.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠ CACHE KEY CONTRACT — for the P9 gateway author:
  The key MUST include: model, role, prompt, schema, AND params.
  Omitting 'model' causes a stale response from a retired model to be
  served silently as if it were from the new candidate — exactly the
  failure mode §5.9 is designed to prevent.
  Key construction belongs in llm/gateway.py, not here.
  Suggested construction:
      import hashlib, json
      key = hashlib.sha256(
          json.dumps(
              {"model": model, "role": role, "prompt": prompt,
               "schema": schema, "params": params},
              sort_keys=True,
          ).encode()
      ).hexdigest()
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This class accepts any pre-computed key string and stores/retrieves
JSON-serialisable values. It knows nothing about what the key encodes.

Layout on disk: {cache_dir}/{key[:2]}/{key}.json
WHY: Two-character prefix sharding limits directory entries to ≤256 per
     shard (65k possible hex prefixes / 256 shards), keeping ls/readdir fast.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


class DiskCache:
    """Content-addressed JSON cache backed by one file per entry."""

    def __init__(self, cache_dir: Path) -> None:
        self._root = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        shard = key[:2]
        return self._root / shard / f"{key}.json"

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value, or None on cache miss."""
        p = self._path(key)
        if not p.exists():
            return None
        with p.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def set(self, key: str, value: Any) -> None:
        """Store value under key (overwrites if already present)."""
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as fh:
            json.dump(value, fh)

    def has(self, key: str) -> bool:
        """Return True if the key exists in the cache."""
        return self._path(key).exists()
