"""``Grid.column_flow`` is the one-cell-to-one-cell convenience.

When the destination (or source) cell exposes multiple primary anchors
-- e.g. a :class:`Row` holding ``Anchor("L", ...)`` and ``Anchor("R",
...)`` side by side -- the library cannot pick which sibling to hit
without guessing the author's intent.  In that case it skips the cell
entirely and the author is expected to declare the flow explicitly
with :class:`Flow` or :class:`Bus`.

This also guarantees that ``column_flow`` never renders a "ghost"
arrow landing in empty space between siblings.
"""
from __future__ import annotations

import re

from sciviz import (Anchor, Box, Canvas, Grid, Row, Theme)
from sciviz.composition import Flow, Flowed


_LINE_RX = re.compile(
    r'<line\s+x1="([-\d.]+)"\s+y1="([-\d.]+)"\s+'
    r'x2="([-\d.]+)"\s+y2="([-\d.]+)"([^/]*)/>'
)


def _lines(svg: str):
    out = []
    for m in _LINE_RX.finditer(svg):
        x1, y1, x2, y2, rest = m.groups()
        out.append({
            "x1": float(x1), "y1": float(y1),
            "x2": float(x2), "y2": float(y2),
            "marker": "marker-end" in rest,
        })
    return out


def _rects(svg: str):
    return [(float(x), float(y), float(w), float(h))
            for x, y, w, h in re.findall(
                r'<rect x="([-\d.]+)" y="([-\d.]+)" '
                r'width="([-\d.]+)" height="([-\d.]+)"[^/]*/>', svg)]


def test_column_flow_skips_multi_anchor_destination():
    """Author declares ``Row(Anchor(L), Anchor(R))`` above a plain
    Box with ``column_flow="up"``.  Library emits NO auto-arrow for
    this pair -- picking a sibling would overstate author intent.
    """
    theme = Theme()
    g = Grid(
        rows=["upper", "lower"],
        columns=[{
            "upper": Row(
                Anchor("L", Box("L", width=60.0, height=22.0)),
                Anchor("R", Box("R", width=60.0, height=22.0)),
            ),
            "lower": Box("Bot", width=80.0, height=22.0),
        }],
        column_flow="up",
    )
    size = g.measure(theme)
    canvas = Canvas()
    g.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    arrowed = [ln for ln in _lines(svg) if ln["marker"]]
    assert arrowed == [], (
        f"column_flow should not emit arrows into multi-anchor "
        f"destinations; got {arrowed}")


def test_column_flow_skips_multi_anchor_source_symmetrically():
    """Same policy in the reverse direction: a multi-anchor lower cell
    has no single axis to emit from, so column_flow skips it.
    """
    theme = Theme()
    g = Grid(
        rows=["upper", "lower"],
        columns=[{
            "upper": Box("Top", width=80.0, height=22.0),
            "lower": Row(
                Anchor("L", Box("L", width=60.0, height=22.0)),
                Anchor("R", Box("R", width=60.0, height=22.0)),
            ),
        }],
        column_flow="up",
    )
    size = g.measure(theme)
    canvas = Canvas()
    g.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    arrowed = [ln for ln in _lines(svg) if ln["marker"]]
    assert arrowed == [], (
        f"column_flow should not emit arrows from multi-anchor "
        f"sources; got {arrowed}")


def test_column_flow_single_anchor_still_draws_straight_arrow():
    """The happy path: two single-anchor cells -- one straight arrow."""
    theme = Theme()
    g = Grid(
        rows=["u", "d"],
        columns=[{
            "u": Box("U", width=80.0, height=22.0),
            "d": Box("D", width=80.0, height=22.0),
        }],
        column_flow="up",
    )
    size = g.measure(theme)
    canvas = Canvas()
    g.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    arrowed = [ln for ln in _lines(svg) if ln["marker"]]
    assert len(arrowed) == 1, arrowed
    ln = arrowed[0]
    assert abs(ln["x1"] - ln["x2"]) < 0.6, ln


def test_author_can_route_multi_anchor_with_explicit_flow():
    """An explicit :class:`Flow` from a single-anchor lower cell into
    a named anchor inside a multi-anchor upper cell draws correctly --
    the author keeps semantic control over which sibling is targeted.
    """
    theme = Theme()
    inner = Grid(
        rows=["upper", "lower"],
        columns=[{
            "upper": Row(
                Anchor("rn_l", Box("L", width=60.0, height=22.0)),
                Anchor("rn_r", Box("R", width=60.0, height=22.0)),
            ),
            "lower": Anchor("emb", Box("Emb", width=80.0, height=22.0)),
        }],
        column_flow="up",
    )
    outer = Flowed(
        inner,
        flows=[Flow("emb", "rn_r", src_side="top", dst_side="bottom",
                    style="orthogonal")],
    )
    size = outer.measure(theme)
    canvas = Canvas()
    outer.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    arrowed = [ln for ln in _lines(svg) if ln["marker"]]
    assert len(arrowed) == 1, (
        f"expected exactly one arrow (from the author's Flow), got {arrowed}")

    rects = _rects(svg)
    R_matches = [r for r in rects
                 if abs(r[2] - 60.0) < 0.5 and abs(r[3] - 22.0) < 0.5]
    assert len(R_matches) == 2, R_matches
    R_matches.sort(key=lambda r: r[0])
    right_cx = R_matches[1][0] + R_matches[1][2] / 2
    right_bot = R_matches[1][1] + R_matches[1][3]
    ln = arrowed[0]
    assert abs(ln["x2"] - right_cx) < 0.6, (
        f"Flow arrow head x {ln['x2']} should match right-RMS cx {right_cx}")
    assert abs(ln["y2"] - right_bot) < 0.6, (
        f"Flow arrow head y {ln['y2']} should touch right-RMS bottom "
        f"{right_bot}")
