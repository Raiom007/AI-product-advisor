"""RunManifest: records the config, code version, and data state that
produced a given AdvisorResponse or eval report.

WHY: eval replay requires proof that "same numbers" means identical
     settings — config hash + git SHA + data hash together satisfy §5.9
     and §13 DoD bullet 3.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RunManifest:
    """Stamped on every AdvisorResponse and eval report."""
    trace_id: str
    config_hash: str    # from load_config()["_hash"]
    profile: str        # from load_config()["_profile"]
    started_at: float = field(default_factory=time.time)
    git_sha: Optional[str] = None       # set by service.py at startup via `git rev-parse HEAD`
    data_hash: Optional[str] = None     # SHA-256 of SQLite + Chroma state files (set by ingest)

    @classmethod
    def build(
        cls,
        trace_id: str,
        config: dict,
        git_sha: Optional[str] = None,
    ) -> "RunManifest":
        """Build a manifest from the result of load_config()."""
        return cls(
            trace_id=trace_id,
            config_hash=config.get("_hash", ""),
            profile=config.get("_profile", "unknown"),
            git_sha=git_sha,
        )

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict for AdvisorResponse.budget_report."""
        return {
            "trace_id": self.trace_id,
            "config_hash": self.config_hash,
            "profile": self.profile,
            "started_at": self.started_at,
            "git_sha": self.git_sha,
            "data_hash": self.data_hash,
        }
