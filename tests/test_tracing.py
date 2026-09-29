"""Tests for core/tracing.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from advisor.core.tracing import Tracer


def test_span_writes_one_jsonl_line(tmp_path):
    tracer = Tracer(trace_id="t1", traces_dir=tmp_path / "traces")
    with tracer.span("tool_call", "retrieve"):
        pass
    lines = (tmp_path / "traces" / "t1.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1


def test_span_json_has_required_fields(tmp_path):
    tracer = Tracer(trace_id="t2", traces_dir=tmp_path / "traces")
    with tracer.span("tool_call", "retrieve") as s:
        s.output_summary = "5 hits"
    data = json.loads((tmp_path / "traces" / "t2.jsonl").read_text())
    assert data["trace_id"] == "t2"
    assert data["type"] == "tool_call"
    assert data["name"] == "retrieve"
    assert data["output_summary"] == "5 hits"
    assert data["latency_ms"] is not None
    assert data["latency_ms"] >= 0


def test_span_records_error_on_exception(tmp_path):
    tracer = Tracer(trace_id="t3", traces_dir=tmp_path / "traces")
    with pytest.raises(ValueError):
        with tracer.span("tool_call", "bad_tool"):
            raise ValueError("simulated error")
    data = json.loads((tmp_path / "traces" / "t3.jsonl").read_text())
    assert data["error"] == "simulated error"
    assert data["latency_ms"] is not None  # still measured on error path


def test_span_writes_even_after_exception(tmp_path):
    """Span must be written in the finally block regardless of exceptions."""
    tracer = Tracer(trace_id="t4", traces_dir=tmp_path / "traces")
    try:
        with tracer.span("plan", "root"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert (tmp_path / "traces" / "t4.jsonl").exists()


def test_parent_child_span_ids_linked(tmp_path):
    tracer = Tracer(trace_id="t5", traces_dir=tmp_path / "traces")
    with tracer.span("plan", "main") as parent:
        parent_id = parent.span_id
        with tracer.span("tool_call", "child_step", parent_id=parent_id):
            pass

    lines = (tmp_path / "traces" / "t5.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    spans = [json.loads(line) for line in lines]
    child = next(s for s in spans if s["name"] == "child_step")
    assert child["parent_id"] == parent_id
    assert child["span_id"] != parent_id


def test_span_without_parent_has_none_parent_id(tmp_path):
    tracer = Tracer(trace_id="t6", traces_dir=tmp_path / "traces")
    with tracer.span("plan", "root"):
        pass
    data = json.loads((tmp_path / "traces" / "t6.jsonl").read_text())
    assert data["parent_id"] is None


def test_multiple_spans_all_valid_jsonl(tmp_path):
    tracer = Tracer(trace_id="t7", traces_dir=tmp_path / "traces")
    for i in range(5):
        with tracer.span("tool_call", f"step_{i}"):
            pass
    lines = (tmp_path / "traces" / "t7.jsonl").read_text().strip().splitlines()
    assert len(lines) == 5
    for line in lines:
        data = json.loads(line)
        assert "trace_id" in data
        assert "span_id" in data


def test_tracer_creates_traces_dir_if_missing(tmp_path):
    nested = tmp_path / "deep" / "nested" / "traces"
    tracer = Tracer(trace_id="t8", traces_dir=nested)
    with tracer.span("plan", "x"):
        pass
    assert (nested / "t8.jsonl").exists()
