"""Tiny synchronous pub/sub event bus.

WHY: Decouples modules for side-effects (e.g. tracing, metrics) without
     introducing async complexity. Streamlit + ThreadPoolExecutor is sync
     throughout (§9 "Concurrency" row), so async events add no value here.

Usage::

    from advisor.core.events import bus

    # Subscribe (usually at module import time)
    bus.subscribe("span_completed", my_handler)

    # Emit (anywhere)
    bus.emit("span_completed", span=span_obj)
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any


class EventBus:
    """Synchronous publish/subscribe bus.

    Handlers are called in registration order.
    Exceptions in handlers propagate to the emitting caller.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable[..., None]) -> None:
        """Register handler to be called when event is emitted."""
        self._handlers[event].append(handler)

    def emit(self, event: str, **kwargs: Any) -> None:
        """Call all handlers subscribed to event, in registration order."""
        for handler in self._handlers[event]:
            handler(**kwargs)

    def clear(self, event: str | None = None) -> None:
        """Remove handlers for one event, or all events (useful in tests)."""
        if event is not None:
            self._handlers[event] = []
        else:
            self._handlers.clear()


# Module-level singleton — imported by modules that need to emit or subscribe.
# WHY: a single shared bus lets modules communicate without explicit wiring;
#      tests call bus.clear() in teardown to prevent handler leakage.
bus = EventBus()
