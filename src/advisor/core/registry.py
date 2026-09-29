"""Generic plug-in registry with feature-flag gating.

Every extension point in the system (tools, ranking signals, fake-review
signals, guardrails, retrievers, providers, eval suites) is an explicitly
registered plug-in. No implicit discovery by directory scanning.

WHY: ADR 0004 — explicit registration makes the set of active extensions
     inspectable at startup and testable in isolation.

Usage::

    from advisor.core.registry import Registry

    my_registry: Registry = Registry("tools")

    @my_registry.register("my_tool")
    def my_tool_impl(state):
        ...

    fn = my_registry.get("my_tool")
    is_on = my_registry.enabled("my_tool", config["features"])

The concrete registries (tools, verifiers, ranking_signals, …) are
instantiated in core/registries.py (P3).
"""
from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

from advisor.core.errors import RegistryError

T = TypeVar("T")


class Registry(Generic[T]):
    """A named store of callables or classes, with feature-flag gating.

    Thread-safety: registration happens at import time (single-threaded);
    get/enabled are read-only and safe to call from ThreadPoolExecutor workers.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._items: dict[str, T] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, item_name: str) -> Callable[[T], T]:
        """Decorator: register a callable under item_name.

        Raises RegistryError on duplicate names so mistakes fail at import
        time rather than silently shadowing an existing entry.
        """
        def decorator(fn: T) -> T:
            if item_name in self._items:
                raise RegistryError(
                    f"Registry '{self.name}': duplicate name '{item_name}'"
                )
            self._items[item_name] = fn
            return fn
        return decorator

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, item_name: str) -> T:
        """Return the registered item; raise RegistryError if not found."""
        if item_name not in self._items:
            raise RegistryError(
                f"Registry '{self.name}': unknown name '{item_name}'"
            )
        return self._items[item_name]

    def all_names(self) -> list[str]:
        """Return all registered names (registered order = insertion order)."""
        return list(self._items.keys())

    # ------------------------------------------------------------------
    # Feature flags
    # ------------------------------------------------------------------

    def enabled(self, item_name: str, features: dict[str, Any]) -> bool:
        """Return True if item_name is enabled in the features config dict.

        Args:
            item_name: name of the registered item.
            features:  the 'features' sub-dict from load_config(), e.g.
                       {"tools": {"parse_query": true, "verify_images": false}, ...}

        WHY: Permissive default (True) — a missing key in features.yaml does
             not silently disable a feature; it must be explicitly set False.
        """
        registry_flags: dict[str, Any] = features.get(self.name, {})
        return bool(registry_flags.get(item_name, True))

    def list_enabled(self, features: dict[str, Any]) -> list[str]:
        """Return names of all registered items that are currently enabled."""
        return [n for n in self._items if self.enabled(n, features)]
