"""Box sub_label (precision tags) should sit cleanly in the bottom-right
corner of the box *without overlapping the main label*.

Representative use: ``Box("RMSNorm", sub_label="FP32")``.  In the DeepSeek
figure the main label is short and the sub_label is a 4-character precision
tag, so the temptation is to pack them into the same horizontal slot.  The
box must allocate enough width and height that:

  * the main label is fully contained in the upper region of the box,
  * the sub_label is fully contained in the bottom-right corner of the box,
  * the two text regions do not intersect.

These invariants are enforced here by parsing the SVG output and checking
the rendered glyph rectangles.
"""
from __future__ import annotations

import re

import pytest

from sciviz import Box, Theme, Canvas


def _render_svg(elem, theme: Theme) -> tuple[str, float, float]:
    canvas = Canvas()
    size = elem.measure(theme)
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size.w, size.h


_TEXT_RX = re.compile(
    r'<text ([^>]*)>([^<]*)</text>',
)


def _parse_texts(svg: str) -> list[dict]:
    """Extract text elements with attributes as a flat list of dicts."""
    out = []
    for m in _TEXT_RX.finditer(svg):
        attrs_raw, content = m.group(1), m.group(2)
        # pull out the attributes we care about
        x = float(re.search(r'x="([^"]+)"', attrs_raw).group(1))
        y = float(re.search(r'y="([^"]+)"', attrs_raw).group(1))
        fs = float(re.search(r'font-size="([^"]+)"', attrs_raw).group(1))
        anchor_m = re.search(r'text-anchor="([^"]+)"', attrs_raw)
        anchor = anchor_m.group(1) if anchor_m else "start"
        out.append({"x": x, "y": y, "fs": fs, "anchor": anchor, "text": content})
    return out


def _text_rect(theme: Theme, t: dict, *, bold: bool = False) -> tuple[float, float, float, float]:
    """Approx rectangle (x0, y0, x1, y1) of a rendered text element."""
    w = theme.text_width(t["text"], t["fs"], bold=bold)
    asc = t["fs"] * 0.88
    desc = t["fs"] * 0.35
    if t["anchor"] == "middle":
        x0 = t["x"] - w / 2
    elif t["anchor"] == "end":
        x0 = t["x"] - w
    else:
        x0 = t["x"]
    x1 = x0 + w
    y1 = t["y"] + desc
    y0 = t["y"] - asc
    return x0, y0, x1, y1


def _rects_overlap(a, b, eps=0.5) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    if ax1 <= bx0 + eps or bx1 <= ax0 + eps:
        return False
    if ay1 <= by0 + eps or by1 <= ay0 + eps:
        return False
    return True


def test_sub_label_does_not_overlap_main_label_short_box():
    """``Box("RMSNorm", sub_label="FP32")`` is the canonical failing case
    in the current renderer -- the box is narrow and the sub_label ran
    into the main label.  After the fix the two rectangles are disjoint.
    """
    theme = Theme()
    box = Box("RMSNorm", sub_label="FP32", text_size="small")
    svg, w, h = _render_svg(box, theme)
    texts = _parse_texts(svg)
    mains = [t for t in texts if t["text"] == "RMSNorm"]
    subs = [t for t in texts if t["text"] == "FP32"]
    assert mains and subs, svg
    main_rect = _text_rect(theme, mains[0])
    sub_rect = _text_rect(theme, subs[0])
    assert not _rects_overlap(main_rect, sub_rect), (
        f"Main label {main_rect} overlaps sub_label {sub_rect}")


def test_sub_label_is_smaller_than_main_label():
    """Precision tags should be visibly smaller than the main label --
    the "extreme bottom-right corner as subscripts" requirement.
    """
    theme = Theme()
    box = Box("RMSNorm", sub_label="FP32", text_size="small")
    svg, _, _ = _render_svg(box, theme)
    texts = _parse_texts(svg)
    mains = [t for t in texts if t["text"] == "RMSNorm"]
    subs = [t for t in texts if t["text"] == "FP32"]
    assert mains and subs
    assert subs[0]["fs"] < mains[0]["fs"] - 0.5, (
        f"sub_label size {subs[0]['fs']} should be smaller than main "
        f"label size {mains[0]['fs']}")


def test_sub_label_sits_in_bottom_right_corner():
    """The sub_label is anchored to the right edge and the bottom edge
    of the box (with a small padding).
    """
    theme = Theme()
    box = Box("Transformer Block", sub_label="FP8 Mixed Precision",
              text_size="small")
    svg, w, h = _render_svg(box, theme)
    texts = _parse_texts(svg)
    subs = [t for t in texts if t["text"] == "FP8 Mixed Precision"]
    assert subs
    x0, y0, x1, y1 = _text_rect(theme, subs[0])
    # right edge of text within small padding of box right edge
    assert x1 <= w + 0.5
    assert w - x1 < 4.0, (w - x1)
    # bottom edge of text within small padding of box bottom
    assert y1 <= h + 0.5
    assert h - y1 < 4.0, (h - y1)
