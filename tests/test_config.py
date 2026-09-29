"""Tests for core/config.py."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from advisor.core.config import load_config, config_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_configs_dir(tmp_path: Path, profile: str = "dev") -> Path:
    """Create a minimal configs/ tree for testing."""
    root = tmp_path / "configs"
    root.mkdir()
    (root / "models.yaml").write_text(
        "roles:\n  parser:\n    candidates: []\n", encoding="utf-8"
    )
    (root / "limits.yaml").write_text(
        "request_budget:\n  max_model_calls: 12\n", encoding="utf-8"
    )
    profiles_dir = root / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "dev.yaml").write_text(
        "llm:\n  provider_override: fake\n", encoding="utf-8"
    )
    (profiles_dir / "prod.yaml").write_text(
        "llm:\n  provider_override: gemini\n", encoding="utf-8"
    )
    return root


# ---------------------------------------------------------------------------
# Basic loading
# ---------------------------------------------------------------------------

def test_loads_base_yaml_files(tmp_path, monkeypatch):
    configs_dir = make_configs_dir(tmp_path)
    monkeypatch.setenv("ADVISOR_PROFILE", "dev")
    config = load_config(configs_dir)
    assert "models" in config
    assert "limits" in config


def test_profile_key_is_set(tmp_path, monkeypatch):
    configs_dir = make_configs_dir(tmp_path)
    monkeypatch.setenv("ADVISOR_PROFILE", "dev")
    config = load_config(configs_dir)
    assert config["_profile"] == "dev"


def test_profile_overlay_is_applied(tmp_path, monkeypatch):
    configs_dir = make_configs_dir(tmp_path)
    monkeypatch.setenv("ADVISOR_PROFILE", "dev")
    config = load_config(configs_dir)
    # dev.yaml sets llm.provider_override: fake
    assert config["llm"]["provider_override"] == "fake"


def test_different_profiles_give_different_results(tmp_path, monkeypatch):
    configs_dir = make_configs_dir(tmp_path)
    monkeypatch.setenv("ADVISOR_PROFILE", "dev")
    config_dev = load_config(configs_dir)
    monkeypatch.setenv("ADVISOR_PROFILE", "prod")
    config_prod = load_config(configs_dir)
    assert config_dev["llm"]["provider_override"] == "fake"
    assert config_prod["llm"]["provider_override"] == "gemini"


def test_missing_profile_file_loads_base_only(tmp_path, monkeypatch):
    configs_dir = make_configs_dir(tmp_path)
    monkeypatch.setenv("ADVISOR_PROFILE", "nonexistent_profile")
    # Should not raise — just returns base config
    config = load_config(configs_dir)
    assert "_hash" in config


# ---------------------------------------------------------------------------
# Config hash stability
# ---------------------------------------------------------------------------

def test_hash_is_present(tmp_path, monkeypatch):
    configs_dir = make_configs_dir(tmp_path)
    monkeypatch.setenv("ADVISOR_PROFILE", "dev")
    config = load_config(configs_dir)
    assert "_hash" in config
    assert len(config["_hash"]) == 64  # SHA-256 hex


def test_hash_is_stable_across_reloads(tmp_path, monkeypatch):
    configs_dir = make_configs_dir(tmp_path)
    monkeypatch.setenv("ADVISOR_PROFILE", "dev")
    config1 = load_config(configs_dir)
    config2 = load_config(configs_dir)
    assert config1["_hash"] == config2["_hash"]


def test_hash_changes_when_yaml_content_changes(tmp_path, monkeypatch):
    configs_dir = make_configs_dir(tmp_path)
    monkeypatch.setenv("ADVISOR_PROFILE", "dev")
    config1 = load_config(configs_dir)
    # Modify a YAML file
    (configs_dir / "limits.yaml").write_text(
        "request_budget:\n  max_model_calls: 99\n", encoding="utf-8"
    )
    config2 = load_config(configs_dir)
    assert config1["_hash"] != config2["_hash"]


def test_hash_changes_when_profile_changes(tmp_path, monkeypatch):
    configs_dir = make_configs_dir(tmp_path)
    monkeypatch.setenv("ADVISOR_PROFILE", "dev")
    config_dev = load_config(configs_dir)
    monkeypatch.setenv("ADVISOR_PROFILE", "prod")
    config_prod = load_config(configs_dir)
    assert config_dev["_hash"] != config_prod["_hash"]
