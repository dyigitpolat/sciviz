"""`Palette.register` lets a diagram define a named semantic colour once
and reference it everywhere, replacing repeated ``Palette.literal("#...")``
calls.
"""
from __future__ import annotations

from sciviz import Palette, Theme
from sciviz.palette import resolve_color


def setup_function():
    # Drop any custom registrations left over between tests.
    Palette.clear_custom()


def test_register_then_resolve_via_custom():
    Palette.register("emb", "#f1ead0")
    ref = Palette.custom("emb")
    assert resolve_color(ref, Theme()) == "#f1ead0"


def test_register_accessible_via_attribute_lookup():
    """After registration, ``Palette.emb`` returns the custom ColorRef."""
    Palette.register("emb_attr", "#c0c8d0")
    ref = Palette.emb_attr
    assert resolve_color(ref, Theme()) == "#c0c8d0"


def test_registered_color_supports_soft_and_dark_variants():
    Palette.register("mycol", "#3b5fa0")
    ref = Palette.custom("mycol")
    soft = resolve_color(ref.soft(), Theme())
    dark = resolve_color(ref.dark(), Theme())
    assert soft != "#3b5fa0" and soft.startswith("#")
    assert dark != "#3b5fa0" and dark.startswith("#")


def test_unknown_custom_raises():
    import pytest
    with pytest.raises(KeyError):
        Palette.custom("definitely_not_registered")


def test_register_does_not_clobber_builtins():
    """Attempting to overshadow a builtin name like 'alert' raises."""
    import pytest
    with pytest.raises(ValueError):
        Palette.register("alert", "#000000")
