"""Ink centring of a short label (``sciviz.inkcenter``, ``Text(..., ink_center=True)``).

A short label in a box (a step number in a cell, a core's name in a tile, a tag in a badge) is centred by its
ink, the extent of its glyph outlines, in both directions. The default stays what it was: a text that does not
ask is drawn exactly as before.
"""
import io
import re

import numpy as np
import pytest

from sciviz import Canvas, DEFAULT_THEME, Text
from sciviz.inkcenter import center_on_ink, ink_box, ink_center, ink_offset

LABELS = [("0", "700"), ("2", "700"), ("L1", "normal"), ("L2", "normal"), ("I4", "700"), ("H10", "normal")]


def _text_xy(svg: str):
    m = re.search(r'<text x="([0-9.\-]+)" y="([0-9.\-]+)"([^>]*)>', svg)
    return float(m.group(1)), float(m.group(2)), m.group(3)


def _render(t: Text, x=10.0, y=20.0):
    c = Canvas()
    t.render(c, x, y, DEFAULT_THEME)
    return c.to_svg(200, 80)


# ---------------------------------------------------------------------------------------------------------
# the measure: the outlines of the face, checked against the font file itself
# ---------------------------------------------------------------------------------------------------------
def test_ink_box_matches_the_glyph_outline_of_the_face():
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.ttLib import TTFont

    from sciviz.core import _fonts

    registry = _fonts._registry_for(DEFAULT_THEME.font_family)
    if registry is None:
        pytest.skip("no font available")
    face = registry.face_for("bold", "normal")
    font = TTFont(str(face.ttf_path))
    glyphs = font.getGlyphSet()
    name = font.getBestCmap()[ord("2")]
    pen = BoundsPen(glyphs)
    glyphs[name].draw(pen)
    x0, y0, x1, y1 = pen.bounds
    k = 100.0 / font["head"].unitsPerEm
    box = ink_box("2", 100.0, DEFAULT_THEME.font_family, bold=True)
    assert box is not None
    assert box[:4] == pytest.approx((x0 * k, y0 * k, x1 * k, y1 * k), abs=0.6)
    assert box[4] == pytest.approx(glyphs[name].width * k, abs=0.6)


def test_ink_box_scales_with_the_size_and_refuses_what_it_cannot_measure():
    a = ink_box("L1", 10.0, DEFAULT_THEME.font_family)
    b = ink_box("L1", 20.0, DEFAULT_THEME.font_family)
    assert a is not None and b is not None
    assert b == pytest.approx(tuple(2.0 * v for v in a))
    assert ink_box("", 10.0) is None
    assert ink_box("a\nb", 10.0) is None
    assert ink_box("   ", 10.0) is None
    assert ink_center("", 10.0) is None


def test_the_advance_box_and_the_line_band_are_not_the_ink():
    """The defect this module answers: "L" does not stand on the centre of its advance box, and a capital's
    ink does not sit on the centre of sciviz's line box."""
    x0, y0, x1, y1, adv = ink_box("L", 100.0, DEFAULT_THEME.font_family)
    assert abs(0.5 * (x0 + x1) - 0.5 * adv) > 1.0            # over 1% of the size off the advance box's centre
    sz = 100.0
    line_centre_over_baseline = 0.88 * sz - 0.5 * DEFAULT_THEME.text_height(sz)
    assert abs(0.5 * (y0 + y1) - line_centre_over_baseline) > 3.0


# ---------------------------------------------------------------------------------------------------------
# Text(..., ink_center=True)
# ---------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("label,weight", LABELS)
def test_text_default_is_drawn_as_before(label, weight):
    plain = _render(Text(label, weight=weight, size=12.0, align="middle"))
    off = _render(Text(label, weight=weight, size=12.0, align="middle", ink_center=False))
    assert plain == off
    t = Text(label, weight=weight, size=12.0, align="middle")
    x, y, attrs = _text_xy(plain)
    w = t.measure(DEFAULT_THEME).w
    assert x == pytest.approx(10.0 + w / 2, abs=0.01)         # the advance box's centre, anchored in the middle
    assert y == pytest.approx(20.0 + 0.88 * 12.0, abs=0.01)   # the line box's baseline
    assert 'text-anchor="middle"' in attrs
    cb = t.content_bbox(DEFAULT_THEME)
    assert cb[0] == 0.0 and cb[2] == pytest.approx(w)


@pytest.mark.parametrize("label,weight", LABELS)
@pytest.mark.parametrize("align", ["start", "middle", "end"])
def test_text_ink_center_puts_the_ink_on_the_centre_of_its_box(label, weight, align):
    size = 12.0
    t = Text(label, weight=weight, size=size, align=align, ink_center=True)
    box = t.measure(DEFAULT_THEME)
    plain = Text(label, weight=weight, size=size).measure(DEFAULT_THEME)
    assert (box.w, box.h) == (plain.w, plain.h)               # the same footprint in the layout
    x, y, attrs = _text_xy(_render(t))
    assert "text-anchor" not in attrs                         # drawn from its pen origin
    x0, y0, x1, y1, _adv = ink_box(label, size, DEFAULT_THEME.font_family, bold=weight == "700")
    ink_cx = x + 0.5 * (x0 + x1)
    ink_cy = y - 0.5 * (y0 + y1)                              # SVG y points down, the ink box up
    assert ink_cx == pytest.approx(10.0 + box.w / 2, abs=0.02)
    assert ink_cy == pytest.approx(20.0 + box.h / 2, abs=0.02)


@pytest.mark.parametrize("label,weight", LABELS)
def test_text_ink_center_reports_its_ink_as_content_box(label, weight):
    t = Text(label, weight=weight, size=12.0, ink_center=True)
    box = t.measure(DEFAULT_THEME)
    cx, cy, cw, ch = t.content_bbox(DEFAULT_THEME)
    assert cx + cw / 2 == pytest.approx(box.w / 2, abs=1e-6)  # a container that centres the content box
    assert cy + ch / 2 == pytest.approx(box.h / 2, abs=1e-6)  # and one that centres the measured box agree
    x0, y0, x1, y1, _adv = ink_box(label, 12.0, DEFAULT_THEME.font_family, bold=weight == "700")
    assert (cw, ch) == pytest.approx((x1 - x0, y1 - y0))
    assert t.first_baseline(DEFAULT_THEME) == pytest.approx(y1)   # the baseline under the content box's top


def test_text_ink_center_leaves_runs_and_rotated_text_as_they_are():
    runs = [("L", {}), ("1", {"weight": "700"})]
    assert _render(Text(runs, ink_center=True)) == _render(Text(runs))
    assert _render(Text("L1", rotate=90, ink_center=True)) == _render(Text("L1", rotate=90))
    assert Text(runs, ink_center=True).content_bbox(DEFAULT_THEME) == Text(runs).content_bbox(DEFAULT_THEME)


# ---------------------------------------------------------------------------------------------------------
# center_on_ink: a matplotlib Text
# ---------------------------------------------------------------------------------------------------------
def _figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(60 / 72, 40 / 72), dpi=720)    # 60 x 40 pt, ten pixels per point
    fig.set_layout_engine("none")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 60)
    ax.set_ylim(0, 40)
    ax.axis("off")
    return plt, fig, ax


def _ink_centre_pt(fig):
    """The centre of the dark pixels of the rendered figure, in points from the lower-left corner."""
    buf = io.BytesIO()
    fig.savefig(buf, format="rgba", dpi=720)
    w, h = (int(round(v)) for v in fig.get_size_inches() * 720)
    img = np.frombuffer(buf.getvalue(), dtype=np.uint8).reshape(h, w, 4)
    dark = img[:, :, 0] < 128
    ys, xs = np.nonzero(dark)
    assert len(xs), "no ink drawn"
    cx = 0.5 * (xs.min() + xs.max() + 1) / 10.0
    cy = (h - 0.5 * (ys.min() + ys.max() + 1)) / 10.0
    return cx, cy


@pytest.mark.parametrize("label,weight", LABELS + [(r"$\Sigma$", "normal"), ("+", "normal")])
def test_center_on_ink_puts_the_ink_of_a_matplotlib_text_on_its_anchor(label, weight):
    plt, fig, ax = _figure()
    try:
        t = ax.text(30.0, 20.0, label, fontsize=14.0, fontweight=weight, color="black", ha="center",
                    va="center_baseline")
        assert center_on_ink(t) is t
        cx, cy = _ink_centre_pt(fig)
        assert cx == pytest.approx(30.0, abs=0.15)
        assert cy == pytest.approx(20.0, abs=0.15)
    finally:
        plt.close(fig)


def test_matplotlib_line_box_alignment_is_off_the_ink():
    """What ``center_on_ink`` answers: the alignment by the face's line box sets a digit under its anchor."""
    plt, fig, ax = _figure()
    try:
        ax.text(30.0, 20.0, "0", fontsize=14.0, fontweight="bold", color="black", ha="center", va="center_baseline")
        _cx, cy = _ink_centre_pt(fig)
        assert 20.0 - cy > 0.1                                # 0.2 pt in DejaVu Sans, 2.5 pt in Noto Sans at 14 pt
    finally:
        plt.close(fig)


def test_center_on_ink_one_direction_and_reference_string():
    plt, fig, ax = _figure()
    try:
        t = center_on_ink(ax.text(5.0, 20.0, "Carry", fontsize=10.0, ha="left", va="center"), horizontal=False)
        assert t.get_horizontalalignment() == "left" and t.get_verticalalignment() == "baseline"
        a = ax.text(5.0, 20.0, "page", fontsize=10.0)
        b = ax.text(5.0, 20.0, "HALL", fontsize=10.0)
        _ax, ay = ink_offset(a, ref="H")
        _bx, by = ink_offset(b, ref="H")
        assert ay == pytest.approx(by)                        # one baseline over a row of labels
        assert ink_offset(a)[1] < ay                          # a descender lowers a word's own ink centre
        u = ax.text(5.0, 20.0, "two\nlines", fontsize=10.0, ha="center", va="center")
        center_on_ink(u)
        assert u.get_horizontalalignment() == "center" and u.get_verticalalignment() == "center"
        r = ax.text(5.0, 20.0, "L1", fontsize=10.0, ha="center", va="center", rotation=90)
        center_on_ink(r)
        assert r.get_horizontalalignment() == "center" and r.get_verticalalignment() == "center"
    finally:
        plt.close(fig)
