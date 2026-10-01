"""Tests for core/prompts.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from advisor.core.prompts import PromptTemplate, list_prompts, load_prompt


def _make_prompts_dir(tmp_path: Path, files: dict[str, str]) -> Path:
    d = tmp_path / "prompts"
    d.mkdir(exist_ok=True)
    for name, content in files.items():
        (d / f"{name}.md").write_text(content, encoding="utf-8")
    return d


# ---------------------------------------------------------------------------
# load_prompt
# ---------------------------------------------------------------------------

def test_load_prompt_returns_named_tuple(tmp_path):
    prompts_dir = _make_prompts_dir(tmp_path, {"parser": "You are a parser."})
    pt = load_prompt("parser", prompts_dir=prompts_dir)
    assert isinstance(pt, PromptTemplate)


def test_load_prompt_text_matches_file(tmp_path):
    content = "Parse the user query into structured output.\n"
    prompts_dir = _make_prompts_dir(tmp_path, {"parser": content})
    pt = load_prompt("parser", prompts_dir=prompts_dir)
    assert pt.text == content


def test_load_prompt_sha256_is_64_hex_chars(tmp_path):
    prompts_dir = _make_prompts_dir(tmp_path, {"composer": "Write a response."})
    pt = load_prompt("composer", prompts_dir=prompts_dir)
    assert len(pt.sha256) == 64
    assert all(c in "0123456789abcdef" for c in pt.sha256)


def test_load_prompt_name_field_matches_argument(tmp_path):
    prompts_dir = _make_prompts_dir(tmp_path, {"summarizer": "Summarize."})
    pt = load_prompt("summarizer", prompts_dir=prompts_dir)
    assert pt.name == "summarizer"


def test_missing_prompt_raises_file_not_found(tmp_path):
    prompts_dir = _make_prompts_dir(tmp_path, {})
    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent", prompts_dir=prompts_dir)


# ---------------------------------------------------------------------------
# Hash changes when content changes
# ---------------------------------------------------------------------------

def test_hash_changes_when_content_changes(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    f = prompts_dir / "composer.md"

    f.write_text("Version 1 content.", encoding="utf-8")
    pt1 = load_prompt("composer", prompts_dir=prompts_dir)

    f.write_text("Version 2 content — different.", encoding="utf-8")
    pt2 = load_prompt("composer", prompts_dir=prompts_dir)

    assert pt1.sha256 != pt2.sha256


def test_same_content_gives_same_hash(tmp_path):
    content = "Identical content."
    prompts_dir = _make_prompts_dir(tmp_path, {"planner": content})
    pt1 = load_prompt("planner", prompts_dir=prompts_dir)
    pt2 = load_prompt("planner", prompts_dir=prompts_dir)
    assert pt1.sha256 == pt2.sha256


# ---------------------------------------------------------------------------
# list_prompts
# ---------------------------------------------------------------------------

def test_list_prompts_returns_names(tmp_path):
    prompts_dir = _make_prompts_dir(tmp_path, {"a": "a", "b": "b", "c": "c"})
    names = list_prompts(prompts_dir=prompts_dir)
    assert set(names) == {"a", "b", "c"}


def test_list_prompts_returns_sorted(tmp_path):
    prompts_dir = _make_prompts_dir(tmp_path, {"z": "z", "a": "a", "m": "m"})
    names = list_prompts(prompts_dir=prompts_dir)
    assert names == sorted(names)


def test_list_prompts_empty_dir(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    assert list_prompts(prompts_dir=prompts_dir) == []


def test_list_prompts_missing_dir_returns_empty(tmp_path):
    missing = tmp_path / "no_such_dir"
    assert list_prompts(prompts_dir=missing) == []
