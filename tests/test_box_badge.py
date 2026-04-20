"""Box badge (top-right corner chip) should sit cleanly without
overlapping the main label.

The ``badge`` parameter is the semantic counterpart to ``sub_label``
but anchored in the TOP-RIGHT corner, so authors can tag a panel with
a section number ("§4") or a version ("v2") without composing a Row +
Spacer by hand.

Representative use: ``Box(Column(...), badge="§4")``.  The box must
allocate enough width and height that:

  * the main label (or element child) stays in the middle region of
    the box, not crashing into the badge,
  * the badge sits in the top-right corner,
  * the two text regions do not intersect.
"""
from __future__ import annotations

import re

from sciviz import Box, Column, Icon, Theme, Canvas, Text


_TEXT_RX = re.compile(r'<text ([^>]*)>([^<]*)</text>')


def _render_svg(elem, theme: Theme) -> tuple[str, float, float]:
    canvas = Canvas()
    size = elem.measure(theme)
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size.w, size.h


def _parse_texts(svg: str) -> list[dict]:
    out = []
    for m in _TEXT_RX.finditer(svg):
        attrs_raw, content = m.group(1), m.group(2)
        x = float(re.search(r'x="([^"]+)"', attrs_raw).group(1))
        y = float(re.search(r'y="([^"]+)"', attrs_raw).group(1))
        fs = float(re.search(r'font-size="([^"]+)"', attrs_raw).group(1))
        a = re.search(r'text-anchor="([^"]+)"', attrs_raw)
        out.append({"x": x, "y": y, "fs": fs,
                    "anchor": a.group(1) if a else "start", "text": content})
    return out


def _text_rect(theme, t, *, bold=False):
    w = theme.text_width(t["text"], t["fs"], bold=bold)
    asc = t["fs"] * 0.88
    desc = t["fs"] * 0.35
    if t["anchor"] == "middle":
        x0 = t["x"] - w / 2
    elif t["anchor"] == "end":
        x0 = t["x"] - w
    else:
        x0 = t["x"]
    return x0, t["y"] - asc, x0 + w, t["y"] + desc


def _overlap(a, b, eps=0.5):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 <= bx0 + eps or bx1 <= ax0 + eps
                or ay1 <= by0 + eps or by1 <= ay0 + eps)


def test_badge_sits_in_top_right_corner():
    theme = Theme()
    box = Box("Encoder", badge="§4")
    svg, w, h = _render_svg(box, theme)
    texts = _parse_texts(svg)
    badges = [t for t in texts if t["text"] == "§4"]
    assert badges, "badge was not rendered"
    bx0, by0, bx1, by1 = _text_rect(theme, badges[0], bold=True)
    # right-anchored within a small padding of the right edge
    assert w - bx1 < 4.0, (w, bx1)
    # top-anchored within a small padding of the top edge
    assert by0 < 4.0, by0


def test_badge_does_not_overlap_main_label():
    theme = Theme()
    box = Box("Encoder", badge="§4")
    svg, _, _ = _render_svg(box, theme)
    texts = _parse_texts(svg)
    mains = [t for t in texts if t["text"] == "Encoder"]
    badges = [t for t in texts if t["text"] == "§4"]
    assert mains and badges
    assert not _overlap(_text_rect(theme, mains[0]),
                        _text_rect(theme, badges[0], bold=True))


def test_badge_grows_box_when_label_short():
    """If the badge is wider than the label, the box must grow so the
    badge fits with its own padding."""
    theme = Theme()
    short = Box("go").measure(theme)
    tagged = Box("go", badge="§RIDICULOUSLY_LONG_BADGE").measure(theme)
    assert tagged.w > short.w, (short.w, tagged.w)


def test_badge_works_with_element_label():
    theme = Theme()
    child = Column(Icon("image"), Text("Image"))
    box = Box(child, badge="§2")
    svg, w, h = _render_svg(box, theme)
    texts = _parse_texts(svg)
    assert any(t["text"] == "§2" for t in texts)
    assert any(t["text"] == "Image" for t in texts)


def test_badge_independent_of_sub_label():
    """``badge`` (top-right) and ``sub_label`` (bottom-right) coexist."""
    theme = Theme()
    box = Box("Module", badge="v2", sub_label="FP8")
    svg, w, h = _render_svg(box, theme)
    texts = _parse_texts(svg)
    labels = {t["text"]: t for t in texts}
    assert {"Module", "v2", "FP8"} <= set(labels)
    bx0, by0, bx1, by1 = _text_rect(theme, labels["v2"], bold=True)
    sx0, sy0, sx1, sy1 = _text_rect(theme, labels["FP8"])
    # badge above sub_label
    assert by1 < sy0
