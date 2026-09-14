"""A fan-in ``Bus`` (many sources, one sink) should render as a **junction**:

  * vertical tap from each source up to a shared horizontal bar,
  * a SINGLE arrow from the centre of the bar to the sink (with arrowhead),
  * an optional label that sits *beside* the bar/arrow, not on top.

The original DeepSeek concatenation figure is the target: two RMSNorm
blocks merge into a Linear Projection via a small "T" with the word
``concatenation`` tucked to the side.
"""
from __future__ import annotations

import re

from sciviz import (Anchor, Box, Row, Column, Theme, Canvas, Spacer)
from sciviz.composition import Bus, Flowed


def _render(body, flows, theme: Theme | None = None) -> tuple[str, float, float]:
    theme = theme or Theme()
    d = Flowed(body, flows=flows)
    size = d.measure(theme)
    canvas = Canvas()
    d.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size.w, size.h


_LINE_RX = re.compile(
    r'<line ([^/>]*?)/>'
)

_ATTR_RX = re.compile(r'(\w[\w-]*)="([^"]*)"')


def _parse_lines(svg: str) -> list[dict]:
    lines = []
    for m in _LINE_RX.finditer(svg):
        attrs = dict(_ATTR_RX.findall(m.group(1)))
        out = {
            "x1": float(attrs["x1"]),
            "y1": float(attrs["y1"]),
            "x2": float(attrs["x2"]),
            "y2": float(attrs["y2"]),
            "marker_end": attrs.get("marker-end"),
            "dasharray": attrs.get("stroke-dasharray"),
        }
        lines.append(out)
    return lines


def test_fan_in_bus_has_exactly_one_arrow_into_sink():
    """Two sources, one sink: only ONE arrow-terminated line segment
    enters the sink (the final stem from the bar to the sink)."""
    theme = Theme()
    left = Anchor("l", Box("L", width=40, height=20))
    right = Anchor("r", Box("R", width=40, height=20))
    sink = Anchor("s", Box("S", width=40, height=20))
    body = Column(sink, Spacer(0, 30), Row(left, Spacer(20, 0), right),
                  gap="md")
    svg, _, _ = _render(body, [
        Bus(sources=["l", "r"], sinks="s", label="concatenation"),
    ])
    lines = _parse_lines(svg)
    arrow_lines = [l for l in lines if l["marker_end"]]
    assert len(arrow_lines) == 1, (
        f"expected 1 arrow line (bar -> sink), got {len(arrow_lines)}")


def test_fan_in_bus_label_does_not_cross_bar():
    """The label must sit clear of every bus line -- taps, bar, and sink
    arrow -- as a 2-D rectangle check. (Historically this test asserted
    1-D x-separation from the sink arrow, which also outlawed the ideal
    placement: the clean pocket centred directly *below* the bar. The
    two-ring placer now finds that pocket, so the assertion checks the
    real property: no label/wire intersection.)"""
    theme = Theme()
    left = Anchor("l", Box("L", width=40, height=20))
    right = Anchor("r", Box("R", width=40, height=20))
    sink = Anchor("s", Box("S", width=40, height=20))
    body = Column(sink, Spacer(0, 30), Row(left, Spacer(20, 0), right),
                  gap="md")
    svg, _, _ = _render(body, [
        Bus(sources=["l", "r"], sinks="s", label="concatenation"),
    ])
    lines = _parse_lines(svg)
    assert len([l for l in lines if l["marker_end"]]) == 1
    # find the "concatenation" label
    m = re.search(
        r'<text ([^>]*?)>concatenation</text>', svg)
    assert m, svg
    attrs = dict(_ATTR_RX.findall(m.group(1)))
    lx = float(attrs["x"])
    ly = float(attrs["y"])
    fs = float(attrs["font-size"])
    lw = theme.text_width("concatenation", fs)
    anchor = attrs.get("text-anchor", "start")
    if anchor == "middle":
        lx0, lx1 = lx - lw / 2, lx + lw / 2
    elif anchor == "end":
        lx0, lx1 = lx - lw, lx
    else:
        lx0, lx1 = lx, lx + lw
    ly0, ly1 = ly - fs, ly + fs * 0.35
    for line in lines:
        sx0, sx1 = sorted((line["x1"], line["x2"]))
        sy0, sy1 = sorted((line["y1"], line["y2"]))
        assert (lx1 <= sx0 or lx0 >= sx1 or ly1 <= sy0 or ly0 >= sy1), (
            f"label rect ({lx0}, {ly0}, {lx1}, {ly1}) crosses "
            f"bus line {line}")


def test_fan_in_bus_has_horizontal_bar_between_sources():
    """A horizontal bar spans above the two sources and is the common
    meeting point; the sink-arrow starts on that bar."""
    theme = Theme()
    left = Anchor("l", Box("L", width=40, height=20))
    right = Anchor("r", Box("R", width=40, height=20))
    sink = Anchor("s", Box("S", width=40, height=20))
    body = Column(sink, Spacer(0, 30), Row(left, Spacer(20, 0), right),
                  gap="md")
    svg, _, _ = _render(body, [
        Bus(sources=["l", "r"], sinks="s", label="concatenation"),
    ])
    lines = _parse_lines(svg)
    horizontals = [l for l in lines
                   if abs(l["y1"] - l["y2"]) < 0.01 and abs(l["x2"] - l["x1"]) > 5]
    assert horizontals, "no horizontal bar found"


_RECT_ATTR_RX = re.compile(r"<rect ([^/>]*?)/>")


def _rect_center_x_by_width(svg: str, w: float) -> float:
    """Center x of the first rect whose width matches ``w``."""
    for m in _RECT_ATTR_RX.finditer(svg):
        attrs = dict(_ATTR_RX.findall(m.group(1)))
        if abs(float(attrs.get("width", -1.0)) - w) < 0.5:
            return float(attrs["x"]) + w / 2.0
    raise AssertionError(f"no rect of width {w} in svg")


def _rect_by_width(svg: str, w: float) -> tuple[float, float, float, float]:
    """(x, y, w, h) of the first rect whose width matches ``w``."""
    for m in _RECT_ATTR_RX.finditer(svg):
        attrs = dict(_ATTR_RX.findall(m.group(1)))
        if abs(float(attrs.get("width", -1.0)) - w) < 0.5:
            return (float(attrs["x"]), float(attrs["y"]),
                    float(attrs["width"]), float(attrs["height"]))
    raise AssertionError(f"no rect of width {w} in svg")


def test_fan_in_rail_bus_enters_sink_at_face_center():
    """A stacked source column forces the side-rail bus form; the single
    entry into the sink must still land at the CENTER of the sink's
    facing edge (jogging along the spine to get there), never at the
    corner where the rail happens to meet the card."""
    theme = Theme()
    sink = Anchor("s", Box("SINK", width=120, height=24))
    chips = Column(*[Anchor(f"c{i}", Box(f"chip {i}", width=80, height=14))
                     for i in range(4)], gap="sm")
    body = Column(sink, Spacer(0, 30), chips, gap="md")
    svg, _, _ = _render(body, [
        Bus([f"c{i}" for i in range(4)], "s"),
    ])
    lines = _parse_lines(svg)
    arrows = [l for l in lines if l["marker_end"]]
    assert len(arrows) == 1, f"expected one sink arrow, got {len(arrows)}"
    entry = arrows[0]
    assert abs(entry["x1"] - entry["x2"]) < 0.5, (
        f"sink entry must be strictly vertical: {entry}")
    face_center = _rect_center_x_by_width(svg, 120.0)
    assert abs(entry["x1"] - face_center) < 1.0, (
        f"sink entry at x={entry['x1']}, face center at x={face_center}")


def test_fan_in_west_rail_bus_enters_sink_at_south_center():
    """The AgentEvolve system-overview topology: a tall sink card with a
    column of five variable-width chips below it, the chip cluster
    sitting slightly EAST of the sink's centre so the side rail exits on
    the WEST.  The bus must climb the west collector rail, jog east
    along the spine in the clear band below the card, and enter the sink
    at the CENTER of its SOUTH edge -- never at the corner where the
    rail meets the card (the pre-fix behaviour clamped the entry to the
    west edge inset)."""
    sink_w, sink_h = 114.0, 90.0
    chip_widths = [96.0, 88.0, 122.0, 100.0, 84.0]
    sink = Anchor("s", Box("SINK", width=sink_w, height=sink_h))
    chips = Column(*[Anchor(f"c{i}", Box(f"chip {i}", width=w, height=14))
                     for i, w in enumerate(chip_widths)], gap="sm")
    # The Spacer shifts the chip cluster east of the sink's centre line,
    # which sends the side rail west (the paper figure's geometry).
    body = Column(sink, Spacer(0, 30), Row(Spacer(24, 0), chips),
                  gap="md")
    svg, _, _ = _render(body, [
        Bus([f"c{i}" for i in range(len(chip_widths))], "s"),
    ])
    lines = _parse_lines(svg)
    sx, sy, sw_, sh_ = _rect_by_width(svg, sink_w)
    sink_bottom = sy + sh_
    sink_center = sx + sw_ / 2.0
    chip_lefts = [_rect_by_width(svg, w)[0] for w in chip_widths]

    # One arrow, strictly vertical, entering the sink's SOUTH edge.
    arrows = [l for l in lines if l["marker_end"]]
    assert len(arrows) == 1, f"expected one sink arrow, got {len(arrows)}"
    entry = arrows[0]
    assert abs(entry["x1"] - entry["x2"]) < 0.5, (
        f"sink entry must be strictly vertical: {entry}")
    entry_x = entry["x1"]
    entry_top = min(entry["y1"], entry["y2"])
    assert abs(entry_top - sink_bottom) < 0.5, (
        f"entry must land on the sink's south edge y={sink_bottom}, "
        f"got y={entry_top}")

    # Edge-CENTER entry (the defect: pre-fix it clamped to the west
    # corner inset at sink.x + edge_inset).
    assert abs(entry_x - sink_center) < 3.0, (
        f"sink entry at x={entry_x}, south-edge center at "
        f"x={sink_center}")

    # The topology really is the west-rail form: a vertical collector
    # runs strictly WEST of every chip.
    verticals = [l for l in lines
                 if abs(l["x1"] - l["x2"]) < 0.5 and not l["marker_end"]]
    assert any(l["x1"] < min(chip_lefts) - 0.5 for l in verticals), (
        f"expected a west collector rail left of x={min(chip_lefts)}; "
        f"verticals at x={sorted(l['x1'] for l in verticals)}")

    # The jog from the rail to the centred entry runs horizontally in
    # the clear band below the card.
    jogs = [l for l in lines
            if abs(l["y1"] - l["y2"]) < 0.5
            and abs(max(l["x1"], l["x2"]) - entry_x) < 0.5]
    assert jogs, "no horizontal jog reaches the centred entry"
    jog_y = jogs[0]["y1"]
    assert sink_bottom < jog_y < min(
        _rect_by_width(svg, w)[1] for w in chip_widths), (
        f"jog at y={jog_y} must run in the clear band between the "
        f"sink bottom ({sink_bottom}) and the topmost chip")


def test_fan_in_walled_center_falls_back_loudly():
    """When the centred descent is genuinely walled (an endpoint rises
    under the sink's south centre), the bar-aligned fallback still
    applies -- but LOUDLY: a UserWarning is emitted and, when a debug
    recorder is active, a note is recorded.  Silent corner entries are
    how the original defect shipped twice."""
    import pytest

    from sciviz.auto.debug import DebugRecorder, record_into

    def render_walled():
        theme = Theme()
        canvas = Canvas()
        # Hand-placed registry (the documented unit-test surface for
        # Bus geometry): the "tall" source overlaps the sink's band and
        # straddles its centre line, so the centred descent must hit it.
        registry = {
            "s":    (0.0, 0.0, 120.0, 30.0),
            "tall": (45.0, 20.0, 30.0, 60.0),
            "west": (0.0, 70.0, 30.0, 14.0),
        }
        bus = Bus(sources=["tall", "west"], sinks="s")
        bus._render(canvas, theme, registry)
        return canvas.to_svg(200.0, 120.0)

    with pytest.warns(UserWarning, match="centred entry.*walled"):
        svg = render_walled()
    lines = _parse_lines(svg)
    arrows = [l for l in lines if l["marker_end"]]
    assert len(arrows) == 1
    entry = arrows[0]
    assert abs(entry["x1"] - entry["x2"]) < 0.5
    # Fallback keeps the bar-aligned entry (off-centre but on the face).
    assert abs(entry["x1"] - 60.0) > 3.0, (
        f"walled entry should NOT be centred, got x={entry['x1']}")
    assert 0.0 < entry["x1"] < 120.0
    assert abs(min(entry["y1"], entry["y2"]) - 30.0) < 0.5

    # The fallback also leaves a debug-recorder note.
    rec = DebugRecorder()
    with pytest.warns(UserWarning), record_into(rec):
        render_walled()
    assert any("walled" in n for n in rec.notes), rec.notes


def test_fan_in_offset_sink_puts_the_spine_in_the_separating_gap():
    """A row of sources feeding one sink set BELOW AND TO THE SIDE.

    The clusters overlap in x and are cleanly separated in y, so the only gap a
    spine can occupy is the horizontal one between the row and the sink. The
    centroid vector leans horizontal here (the sink is offset far enough right
    that dx exceeds dy), and orienting on the centroid alone therefore laid a
    VERTICAL spine straight across the sink card, landing the arrowhead inside
    the box and leaving the outer taps dangling. Auto-orientation must pick the
    axis on which the clusters actually separate.
    """
    theme = Theme()
    cards = Row(*[Anchor(f"q{i}", Box(f"RQ{i}", width=70, height=30))
                  for i in range(4)], gap="sm")
    sink = Anchor("j", Box("JOINT", width=90, height=30))
    body = Column(cards, Spacer(0, 40),
                  Row(Spacer(210, 0), sink), gap="md")
    svg, _, _ = _render(body, [
        Bus(sources=[f"q{i}" for i in range(4)], sinks="j"),
    ])
    lines = _parse_lines(svg)
    arrows = [l for l in lines if l["marker_end"]]
    assert len(arrows) == 1, f"expected one sink arrow, got {len(arrows)}"
    entry = arrows[0]
    assert abs(entry["x1"] - entry["x2"]) < 0.5, (
        f"the sink is below the sources, so its entry must be vertical: {entry}")

    _, sink_top, _, _ = _rect_by_width(svg, 90.0)
    for seg in lines:
        if seg["marker_end"]:
            continue
        assert min(seg["y1"], seg["y2"]) <= sink_top + 0.5, (
            f"no bus segment may run past the sink's top edge into its body: "
            f"{seg} against sink top {sink_top}")
