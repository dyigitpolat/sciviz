"""Ink centring of a short label: its glyph outlines, not its advance box and line box, stand on the centre.

A text engine centres a string by two boxes that are not its ink. Horizontally it uses the advance box, the
pen's travel, which carries the side bearings of the first and the last glyph ("L1" in Noto Sans has 0.42 pt
more white on its right at 7 pt). Vertically it uses the line box of the face, from the descender line to the
ascender line, or the part of it above the baseline. A digit or a capital fills neither: at 7 pt in Noto Sans
matplotlib's ``va="center_baseline"`` sets the ink 1.2 pt under the anchor and ``va="center"`` 0.2 pt under it,
and sciviz's own line band sets it about 0.4 pt over the centre. In a running label the offset is one constant
and nobody sees it. In a small box (a step number in a cell, a core's name in a tile, a tag in a badge) it is a
visible share of the box's padding, and the label reads as off centre.

Two entry points share one definition of the ink (the extent of the glyph outlines of the string in the face
that draws it):

- :func:`ink_box` measures a string in a sciviz font stack (the faces the exporters outline). ``Text(...,
  ink_center=True)`` uses it to draw a one-line label with its ink on the centre of its measured box.
- :func:`center_on_ink` moves a matplotlib ``Text`` (a figure drawn with matplotlib beside sciviz diagrams) so
  the centre of its ink stands on its anchor, in both directions or in one.

Both are opt-in: a text that does not ask is drawn exactly as before.
"""
from __future__ import annotations

import functools
from typing import Optional, Tuple

__all__ = ["ink_box", "ink_center", "center_on_ink", "ink_offset", "ink_gap", "keep_clear_of_discs"]

_REF = 100.0        # the size the outlines are measured at (the result scales linearly with the size)


@functools.lru_cache(maxsize=4096)
def _ink_box_at_ref(text: str, font_family: Optional[str], bold: bool,
                    italic: bool) -> Optional[Tuple[float, float, float, float, float]]:
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath

    from .core import _fonts

    registry = _fonts._registry_for(font_family)
    if registry is None or not text or "\n" in text:
        return None
    face = registry.face_for("bold" if bold else "normal", "italic" if italic else "normal")
    fallbacks = _fonts._fallback_faces(font_family, bold, italic)
    pen, box = 0.0, None
    try:
        for segment, seg_face in _fonts._segment_by_coverage(text, face.ttf_path, fallbacks):
            prop = FontProperties(fname=str(seg_face), size=_REF)
            ext = TextPath((0, 0), segment, size=_REF, prop=prop, usetex=False).get_extents()
            adv = _fonts._text_to_path().get_text_width_height_descent(segment, prop, False)[0]
            if ext.width > 0 and ext.height > 0:
                seg = (pen + ext.x0, ext.y0, pen + ext.x1, ext.y1)
                box = seg if box is None else (min(box[0], seg[0]), min(box[1], seg[1]),
                                               max(box[2], seg[2]), max(box[3], seg[3]))
            pen += float(adv)
    except Exception:
        return None
    if box is None:
        return None
    return box + (pen,)


def ink_box(text: str, size: float, font_family: Optional[str] = None, *, bold: bool = False,
            italic: bool = False) -> Optional[Tuple[float, float, float, float, float]]:
    """``(x0, y0, x1, y1, advance)`` of one line of text at ``size``: the box of its glyph outlines about the pen
    origin (x to the right, y UP from the baseline) and its advance width, in the units of ``size``.

    Measured in the sciviz font stack ``font_family`` (the theme's ``font_family``; the faces the exporters
    outline), per glyph through the stack as the width measure does. ``None`` for an empty or multi-line string,
    a string without ink, or when no font is available.
    """
    ref = _ink_box_at_ref(text, font_family, bool(bold), bool(italic))
    if ref is None:
        return None
    k = float(size) / _REF
    return tuple(v * k for v in ref)


def ink_center(text: str, size: float, font_family: Optional[str] = None, *, bold: bool = False,
               italic: bool = False) -> Optional[Tuple[float, float]]:
    """``(cx, cy)``: the centre of the ink of one line of text, right of the pen origin and above the baseline."""
    box = ink_box(text, size, font_family, bold=bold, italic=italic)
    if box is None:
        return None
    return 0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])


# ---------------------------------------------------------------------------------------------------------
# matplotlib
# ---------------------------------------------------------------------------------------------------------
def _mpl_ink(t, s: str):
    """The extent of the outlines of ``s`` set as the matplotlib text ``t`` is set (its face, size, math mode),
    in points about the pen origin; ``None`` without ink."""
    from matplotlib.textpath import TextPath

    fp = t.get_fontproperties()
    try:
        ext = TextPath((0, 0), s, size=fp.get_size_in_points(), prop=fp, usetex=False).get_extents()
    except Exception:
        return None
    if not (ext.width > 0 and ext.height > 0):
        return None
    return ext


def ink_offset(t, *, ref: Optional[str] = None) -> Optional[Tuple[float, float]]:
    """``(cx, cy)`` in points: the centre of the ink of a one-line matplotlib ``Text`` right of its pen origin and
    above its baseline. ``ref``: a string whose ink gives the vertical centre in place of the label's own (a
    word with a descender is then centred as its capitals are: ``ref="H"``)."""
    s = t.get_text()
    if not s.strip() or "\n" in s:
        return None
    ext = _mpl_ink(t, s)
    if ext is None:
        return None
    cy = 0.5 * (ext.y0 + ext.y1)
    if ref:
        rext = _mpl_ink(t, ref)
        if rext is not None:
            cy = 0.5 * (rext.y0 + rext.y1)
    return 0.5 * (ext.x0 + ext.x1), cy


def center_on_ink(t, *, horizontal: bool = True, vertical: bool = True, ref: Optional[str] = None):
    """Move a one-line, unrotated matplotlib ``Text`` so the centre of its INK stands on its anchor.

    The text's position (``t.get_position()``, in its own transform) stays the anchor. ``horizontal`` and
    ``vertical`` choose the directions: a direction that is off keeps the text's own alignment. The text is
    re-anchored at its pen origin (``ha="left"`` and/or ``va="baseline"``) and shifted by the measured ink
    centre through an offset in points, so the result holds in any coordinate system and at any dpi.

    ``ref``: a string whose ink sets the vertical centre in place of the label's own, for one baseline over a
    row of labels or for a word with a descender (``ref="H"``).

    Returns ``t``. A multi-line, rotated or inkless text is returned unchanged.
    """
    from matplotlib.transforms import ScaledTranslation

    if not (horizontal or vertical) or t.get_rotation() % 360:
        return t
    off = ink_offset(t, ref=ref)
    if off is None or t.figure is None:
        return t
    cx, cy = off
    dx = dy = 0.0
    if horizontal:
        t.set_horizontalalignment("left")
        dx = -cx
    if vertical:
        t.set_verticalalignment("baseline")
        dy = -cy
    t.set_transform(t.get_transform() + ScaledTranslation(dx / 72.0, dy / 72.0, t.figure.dpi_scale_trans))
    return t


# ---------------------------------------------------------------------------------------------------------
# [aad:build] a line of text keeps a floor of white from the disc marks beside it, whatever the value it prints
# ---------------------------------------------------------------------------------------------------------
def _ink_polygons(t):
    """The glyph outlines of a one-line matplotlib ``Text`` as drawn, in display pixels (closed polygons, curves
    flattened), its pen origin the left end of its line box on its baseline."""
    from matplotlib.textpath import TextPath

    fig = t.figure
    r = fig.canvas.get_renderer()
    fp = t.get_fontproperties()
    bb = t.get_window_extent(r)
    probe = fig.text(0, 0, "x", fontproperties=fp, va="baseline")
    line_desc = -probe.get_window_extent(r).y0
    probe.remove()
    _w, _h, d = r.get_text_width_height_descent(t.get_text(), fp, False)
    px = fig.dpi / 72.0
    path = TextPath((0, 0), t.get_text(), size=fp.get_size_in_points(), prop=fp)
    return [poly * px + (bb.x0, bb.y0 + max(d, line_desc)) for poly in path.to_polygons(closed_only=False)]


def ink_gap(t, centre, radius: float) -> float:
    """The least white, in points, between the glyph outlines of a one-line matplotlib ``Text`` and the edge of a disc
    (``centre`` in display pixels, ``radius`` in points); ``inf`` for a text without ink."""
    import numpy as np

    if not t.get_text().strip():
        return float("inf")
    px = t.figure.dpi / 72.0
    c = np.asarray(centre, dtype=float)
    best = float("inf")
    for poly in _ink_polygons(t):
        if len(poly) < 2:
            continue
        a, b = poly[:-1], poly[1:]
        ab = b - a
        u = np.clip(((c - a) * ab).sum(axis=1) / np.maximum((ab * ab).sum(axis=1), 1e-12), 0.0, 1.0)
        best = min(best, float(np.hypot(*(a + ab * u[:, None] - c).T).min()) / px - radius)
    return best


def _shift(t, dy: float):
    """Move a text up by ``dy`` points: an annotation in offset points by its offset, any other text by its transform."""
    from matplotlib.text import Annotation
    from matplotlib.transforms import ScaledTranslation

    if isinstance(t, Annotation) and t.anncoords in ("offset points", ("offset points", "offset points")):
        x, y = t.xyann
        t.xyann = (x, y + dy)
    else:
        t.set_transform(t.get_transform() + ScaledTranslation(0.0, dy / 72.0, t.figure.dpi_scale_trans))


def keep_clear_of_discs(lines, discs, clear: float, *, step: float = 0.02, limit: float = 2.0):
    """Keep every line of text at least ``clear`` points of white from every disc mark.

    ``lines``: groups of one-line, unrotated matplotlib texts that share a baseline and move together (a row's name,
    its value and its tag). ``discs``: ``(cx, cy, radius)``, the centre in display pixels and the radius in points. A
    line that stands closer than ``clear`` to a disc moves as a whole away from that disc (up when the disc's centre
    lies under the middle of the line's ink, else down) by the least multiple of ``step`` points that gives ``clear``
    to every disc; every other line stays where it is. Returns each line's shift in points (0.0 for a line that
    stays). A line that cannot reach ``clear`` within ``limit`` points is refused (``ValueError``), never left close.
    """
    out = []
    for line in lines:
        line = [t for t in line if t.get_text().strip()]
        if not line:
            out.append(0.0)
            continue
        fig = line[0].figure
        fig.canvas.draw()

        def least():
            best = None
            for t in line:
                for cx, cy, rad in discs:
                    g = ink_gap(t, (cx, cy), rad)
                    if best is None or g < best[0]:
                        best = (g, cy, t)
            return best

        got = least()
        if got is None or got[0] >= clear:
            out.append(0.0)
            continue
        bb = got[2].get_window_extent(fig.canvas.get_renderer())
        sign = 1.0 if got[1] < 0.5 * (bb.y0 + bb.y1) else -1.0
        moved = 0.0
        while got[0] < clear:
            if abs(moved) + step > limit + 1e-9:
                raise ValueError(f"keep_clear_of_discs: the line {[t.get_text() for t in line]!r} stands "
                                 f"{got[0]:.2f} pt from a disc after a shift of {moved:.2f} pt (limit {limit} pt)")
            for t in line:
                _shift(t, sign * step)
            moved += sign * step
            got = least()
        out.append(round(moved, 6))
    return out
