"""Tests for core/cache.py."""
from __future__ import annotations

import json
from pathlib import Path

from advisor.core.cache import DiskCache


def test_miss_returns_none(tmp_path):
    cache = DiskCache(tmp_path / "cache")
    assert cache.get("nonexistent_key_abc123") is None


def test_has_returns_false_on_miss(tmp_path):
    cache = DiskCache(tmp_path / "cache")
    assert cache.has("missing") is False


def test_set_and_get_roundtrip_dict(tmp_path):
    cache = DiskCache(tmp_path / "cache")
    value = {"role": "parser", "output": {"parsed": True}, "tokens": 42}
    cache.set("key1abc", value)
    assert cache.get("key1abc") == value


def test_set_and_get_roundtrip_list(tmp_path):
    cache = DiskCache(tmp_path / "cache")
    cache.set("listkey", [1, 2, 3])
    assert cache.get("listkey") == [1, 2, 3]


def test_set_and_get_roundtrip_string(tmp_path):
    cache = DiskCache(tmp_path / "cache")
    cache.set("strkey", "hello world")
    assert cache.get("strkey") == "hello world"


def test_has_true_after_set(tmp_path):
    cache = DiskCache(tmp_path / "cache")
    cache.set("present", 42)
    assert cache.has("present") is True


def test_different_keys_do_not_collide(tmp_path):
    cache = DiskCache(tmp_path / "cache")
    cache.set("key_aaaa", "value_a")
    cache.set("key_bbbb", "value_b")
    assert cache.get("key_aaaa") == "value_a"
    assert cache.get("key_bbbb") == "value_b"


def test_overwrite_replaces_value(tmp_path):
    cache = DiskCache(tmp_path / "cache")
    cache.set("over", "old_value")
    cache.set("over", "new_value")
    assert cache.get("over") == "new_value"


def test_sharding_uses_key_prefix(tmp_path):
    """Files are stored under {cache_dir}/{key[:2]}/{key}.json."""
    cache = DiskCache(tmp_path / "cache")
    cache.set("abcdef1234", "val")
    shard_dir = tmp_path / "cache" / "ab"
    assert shard_dir.is_dir()
    assert (shard_dir / "abcdef1234.json").exists()


def test_shard_file_is_valid_json(tmp_path):
    cache = DiskCache(tmp_path / "cache")
    cache.set("xyzabc", {"k": "v"})
    p = tmp_path / "cache" / "xy" / "xyzabc.json"
    with p.open() as fh:
        data = json.load(fh)
    assert data == {"k": "v"}


def test_cache_dir_created_automatically(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    cache = DiskCache(nested)
    cache.set("k", 1)
    assert cache.get("k") == 1
