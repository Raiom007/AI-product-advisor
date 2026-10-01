"""Tests for core/registry.py."""
from __future__ import annotations

import pytest

from advisor.core.errors import RegistryError
from advisor.core.registry import Registry

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_and_get():
    reg: Registry = Registry("tools")

    @reg.register("my_tool")
    def my_tool():
        return 42

    assert reg.get("my_tool")() == 42


def test_get_unknown_raises():
    reg: Registry = Registry("tools")
    with pytest.raises(RegistryError, match="unknown name 'nonexistent'"):
        reg.get("nonexistent")


def test_duplicate_name_raises():
    reg: Registry = Registry("tools")

    @reg.register("dup")
    def dup1():
        pass

    with pytest.raises(RegistryError, match="duplicate name 'dup'"):
        @reg.register("dup")
        def dup2():
            pass


def test_all_names_preserves_insertion_order():
    reg: Registry = Registry("signals")

    @reg.register("alpha")
    def alpha(): pass

    @reg.register("beta")
    def beta(): pass

    assert reg.all_names() == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

def test_enabled_true_by_default_when_registry_missing_from_features():
    reg: Registry = Registry("tools")

    @reg.register("active")
    def active(): pass

    assert reg.enabled("active", {}) is True


def test_enabled_true_when_flag_true():
    reg: Registry = Registry("tools")

    @reg.register("my_tool")
    def my_tool(): pass

    features = {"tools": {"my_tool": True}}
    assert reg.enabled("my_tool", features) is True


def test_enabled_false_when_flag_false():
    reg: Registry = Registry("tools")

    @reg.register("disabled_tool")
    def disabled_tool(): pass

    features = {"tools": {"disabled_tool": False}}
    assert reg.enabled("disabled_tool", features) is False


def test_list_enabled_filters_correctly():
    reg: Registry = Registry("tools")

    @reg.register("a")
    def a(): pass

    @reg.register("b")
    def b(): pass

    @reg.register("c")
    def c(): pass

    features = {"tools": {"a": True, "b": False, "c": True}}
    assert reg.list_enabled(features) == ["a", "c"]


def test_list_enabled_empty_registry():
    reg: Registry = Registry("tools")
    assert reg.list_enabled({}) == []


def test_separate_registries_are_independent():
    reg_a: Registry = Registry("tools")
    reg_b: Registry = Registry("signals")

    @reg_a.register("x")
    def xa(): pass

    @reg_b.register("x")
    def xb(): pass  # same name, different registry — should not raise

    assert reg_a.get("x") is xa
    assert reg_b.get("x") is xb
