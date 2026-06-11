"""Target-width fitting: ``Diagram(target_width_pt=...)``.

A paper figure declares the physical width it will occupy on the page
(e.g. 252 pt for an IEEE column) and the library guarantees the theme's
font tokens mean FINAL printed points at that width.  The diagram
compresses LAYOUT (wrap budgets, gaps, padding) -- never fonts -- until
the canvas approaches the target, widens an under-target canvas to
exactly the target, and warns when content cannot fit at the authored
font sizes.
"""
from __future__ import annotations

import re
import warnings

import pytest

from sciviz import Box, Card, Diagram, Palette, Row, Theme, card_header


TARGET = 252.0  # IEEE \columnwidth in points


def _wrappy_card(title: str) -> Card:
    """A card whose chips carry multi-word labels the wrap budget can
    compress (the realistic 'too wide for one column' content shape)."""
    role = Palette.blue
    return Card(
        card_header(title),
        Box("first long descriptive label", wrap=True, text_size="tiny",
            fill=role.soft(), stroke=role),
        Box("second long descriptive label", wrap=True, text_size="tiny",
            fill=role.soft(), stroke=role),
        role=role,
    )


def _wide_body() -> Row:
    """Intrinsically wider than one column, but compressible under it."""
    return Row(_wrappy_card("Alpha"), _wrappy_card("Beta"),
               _wrappy_card("Gamma"), gap="md", equal_widths=True)


def test_target_width_canvas_lands_on_target():
    """A compressible diagram exports at (almost exactly) the target
    width: the layout compresses under it, then pads out to it."""
    d = Diagram.for_paper(_wide_body(), target_width_pt=TARGET)
    intrinsic = Diagram.for_paper(_wide_body()).measure()
    assert intrinsic.w > TARGET, "fixture must start wider than the target"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        d.render()
    assert d._last_render_size.w == pytest.approx(TARGET, rel=0.05)


def test_target_width_fonts_keep_authored_size():
    """Fitting compresses layout only: every emitted font-size matches an
    authored theme token, and the document is pinned to physical points
    so one canvas unit prints as one point (scale 1.0 at the target)."""
    theme = Theme()
    d = Diagram.for_paper(_wide_body(), target_width_pt=TARGET, theme=theme)
    svg = d.render()
    sizes = {float(s) for s in re.findall(r'font-size="([0-9.]+)"', svg)}
    authored = {theme.font_tiny, theme.font_small, theme.font_micro,
                theme.font_label, theme.font_section}
    assert sizes, "fixture must emit text"
    for s in sizes:
        assert any(abs(s - a) < 0.05 for a in authored), (
            f"font-size {s} is not an authored token; fitting must never "
            f"scale fonts")
    # Physical pinning: width="252pt" with a matching 252-unit viewBox.
    assert re.search(r'<svg [^>]*width="252pt"', svg)
    assert re.search(r'<svg [^>]*height="[0-9.]+pt"', svg)


def test_target_width_overflow_warns_instead_of_shrinking():
    """Content that cannot compress to the target (one giant unbreakable
    label) keeps its size and fonts, and warns the author to reduce
    content -- mentioning the legibility floor it would break."""
    d = Diagram.for_paper(Box("W" * 120, text_size="label"),
                          target_width_pt=TARGET)
    with pytest.warns(UserWarning, match="reduce content") as rec:
        svg = d.render()
    assert any("legibility floor" in str(w.message) for w in rec)
    # Fonts stay authored even in the overflow case.
    assert f'font-size="{Theme().font_label:g}"' in svg
    assert d._last_render_size.w > TARGET


def test_default_behavior_unchanged_without_target():
    """``target_width_pt=None`` (the default) keeps the legacy output:
    no physical size attributes, no theme compression."""
    d = Diagram.for_paper(_wide_body())
    svg = d.render()
    assert not re.search(r'<svg [^>]*width="', svg)
    assert not re.search(r'<svg [^>]*height="', svg)
    assert d._layout_theme() is d.theme
