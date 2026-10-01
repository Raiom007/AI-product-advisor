"""JSONL request tracer — one file per request at data/traces/{trace_id}.jsonl.

Span schema (§5.11):
  trace_id, span_id, parent_id, ts, type, name,
  input_summary, output_summary, latency_ms,
  model, tokens_in, tokens_out, cache_hit, error

WHY: JSONL-per-request is the SOW-specified format (§5.11). Each line is
     independently parseable; the UI trace tab streams and renders it; the
     eval harness counts calls and measures latency from the same file.

Usage::

    tracer = Tracer(trace_id="abc123", traces_dir=Path("data/traces"))

    with tracer.span("tool_call", "retrieve") as s:
        results = do_retrieve()
        s.output_summary = f"{len(results)} hits"

    # Nested spans — pass parent_id to link them
    with tracer.span("model_call", "parse_query", parent_id=plan_span_id) as s:
        s.model = "gemini-flash"
        response = call_llm()
        s.tokens_in = response.usage.input
        s.tokens_out = response.usage.output
        s.cache_hit = False
"""
from __future__ import annotations

import json
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

SpanType = Literal[
    "plan", "tool_call", "model_call", "verify", "decision", "budget", "degrade"
]


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_id: str | None
    ts: float
    type: SpanType
    name: str
    input_summary: str | None = None
    output_summary: str | None = None
    latency_ms: float | None = None
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cache_hit: bool | None = None
    error: str | None = None


class Tracer:
    """Writes spans as JSONL lines to a per-request trace file.

    Thread-safe for concurrent span writes (each write is a single
    fh.write() call which is atomic on all major OS/filesystems at
    the sizes used here).
    """

    def __init__(self, trace_id: str, traces_dir: Path) -> None:
        self.trace_id = trace_id
        self._path = traces_dir / f"{trace_id}.jsonl"
        traces_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def span(
        self,
        span_type: SpanType,
        name: str,
        parent_id: str | None = None,
        **kwargs,
    ) -> Generator[Span, None, None]:
        """Context manager: yields a mutable Span, writes it on exit.

        latency_ms is measured automatically.
        If an exception escapes the block, span.error is set before writing.
        """
        s = Span(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()),
            parent_id=parent_id,
            ts=time.time(),
            type=span_type,
            name=name,
            **kwargs,
        )
        t0 = time.monotonic()
        try:
            yield s
        except Exception as exc:
            s.error = str(exc)
            raise
        finally:
            s.latency_ms = round((time.monotonic() - t0) * 1000, 1)
            self._write(s)

    def _write(self, span: Span) -> None:
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(span)) + "\n")
