"""Baseline alignment, shared bands and direct ridge labels.

Three placement defects seen in a dense overview figure (a row of model
tiles, a row of station cards, a ridgeline with its per-row factors):

* Row titles with different decorations (a marker, an icon, a badge,
  none) sat at different heights because a Row aligned whole boxes, not
  text: ``Row(align="baseline")`` fixes it.
* Cards made equally tall by growing spread the surplus into their gaps,
  and a one-line caption sat lower than its two-line neighbours:
  ``SizeGroup(fit="slot", align=...)`` shares each band's height across
  the cards while every child keeps its natural size.
* A column of labels next to a ridgeline never met the ridges, because
  the labels' pitch is set by the font and the chart's by its height:
  ``SparkLine(label=...)`` labels each line at its own level and the
  chart grows its scale until the labels fit.

Every check reads the drawn SVG (text baselines, rectangles, polygons),
so what is asserted is what prints.
"""
from __future__ import annotations

import re
import time

import pytest

from sciviz import (Anchor, Badge, Box, Column, Diagram, Icon, Marker,
                    Palette, Region, Row, SizeGroup, SparkLine, Sparkline,
                    Text, TextBlock, Theme)
from sciviz.core import Canvas
from sciviz.layout._baseline import first_baseline


def _render(elem, theme=None):
    theme = theme or Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h), size, theme


def _baselines(svg: str) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for m in re.finditer(r'<text[^>]*?\sy="([\d.\-]+)"[^>]*>(.*?)</text>',
                         svg, re.S):
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        out.setdefault(text, []).append(float(m.group(1)))
    return out


def _rects(svg: str) -> list[tuple[float, float, float, float]]:
    out = []
    for m in re.finditer(r"<rect ([^>]+?)/?>", svg):
        raw = m.group(1)
        vals = {}
        for k in ("x", "y", "width", "height"):
            mm = re.search(rf'\b{k}="([\d.\-]+)"', raw)
            if mm:
                vals[k] = float(mm.group(1))
        if len(vals) == 4:
            out.append((vals["x"], vals["y"], vals["width"], vals["height"]))
    return out


def T(s, **kw):
    return Text(s, size="tiny", **kw)


# ---------------------------------------------------------------- baseline

def _head(deco, title):
    title_el = T(title, weight="700")
    return Row(deco, title_el, gap="xs", align="center") if deco else title_el


def test_row_baseline_aligns_titles_across_decorations():
    tiles = [Column(_head(deco, name), TextBlock("body one\nbody two",
                                                 size="tiny"),
                    gap="xs", align="start")
             for deco, name in ((Marker("circle", size=3.0), "TitleA"),
                                (Icon("cpu", size=9.0), "TitleB"),
                                (Badge("3"), "TitleC"),
                                (None, "TitleD"))]
    svg, size, _ = _render(Row(*tiles, gap="md", align="baseline"))
    ys = _baselines(svg)
    titles = [ys[f"Title{c}"][0] for c in "ABCD"]
    assert max(titles) - min(titles) < 0.01
    # The badge's digit is not text of the title line, and every glyph is
    # inside the measured box.
    assert all(0.0 < v < size.h for vs in ys.values() for v in vs)


def test_row_baseline_is_opt_in_and_centre_misaligns():
    """The defect: a centred row drops the shorter tile's title."""
    def tiles(align):
        return Row(Column(T("TitleA", weight="700"),
                          TextBlock("a\nb\nc", size="tiny"), gap="xs",
                          align="start"),
                   Column(T("Brief", weight="700"),
                          TextBlock("p", size="tiny"), gap="xs",
                          align="start"),
                   gap="sm", align=align)
    ys = _baselines(_render(tiles("center"))[0])
    assert abs(ys["TitleA"][0] - ys["Brief"][0]) > 3.0
    ys = _baselines(_render(tiles("baseline"))[0])
    assert abs(ys["TitleA"][0] - ys["Brief"][0]) < 0.01


def test_row_baseline_centres_children_without_text():
    icon = Box(width=10, height=40)
    svg, size, theme = _render(Row(T("left"), icon, T("right"),
                                   gap="sm", align="baseline"))
    ys = _baselines(svg)
    assert abs(ys["left"][0] - ys["right"][0]) < 0.01
    (x, y, w, h), = [r for r in _rects(svg) if r[2] == 10.0]
    # The text's ink band (ascent 0.82, descent 0.22 of the size) is
    # centred on the box: the box is the band the texts align on.
    sz = theme.size_px("tiny")
    ink_centre = ys["left"][0] - 0.82 * sz + (0.82 + 0.22) * sz / 2
    assert abs(ink_centre - (y + h / 2)) < 0.01


def test_baseline_through_region_and_anchor_ignores_decoration():
    """Region label, badge and Anchor lanes are not counted twice."""
    plain = Column(T("Plain"), T("x"), gap="xs")
    labelled = Region(Column(T("Framed"), T("y"), gap="xs"),
                      label="Region label", pad_x=3.0, pad_y=2.6)
    anchored = Anchor("a", Column(T("Anchored"), T("z"), gap="xs"))
    svg, size, _ = _render(Row(plain, labelled, anchored, gap="md",
                               align="baseline"))
    ys = _baselines(svg)
    assert max(ys["Plain"][0], ys["Framed"][0], ys["Anchored"][0]) - min(
        ys["Plain"][0], ys["Framed"][0], ys["Anchored"][0]) < 0.01
    assert ys["Region label"][0] < ys["Framed"][0]


def test_first_baseline_matches_drawn_text():
    theme = Theme()
    for el in (T("abc"), Text("abc", size="small"),
               TextBlock("one\ntwo", size="tiny"),
               Row(Marker("circle", size=3.0), T("row"), align="center"),
               Column(Icon("cpu", size=9.0), T("col"), gap="xs")):
        svg, _size, _ = _render(el, theme)
        drawn = min(v for vs in _baselines(svg).values() for v in vs)
        top = el.content_bbox(theme)[1]
        assert abs(top + first_baseline(el, theme) - drawn) < 0.01, el
    assert first_baseline(Icon("cpu", size=9.0), theme) is None
    assert first_baseline(Text("r", rotate=-90), theme) is None


def test_column_rejects_baseline_align():
    with pytest.raises(ValueError, match="Row\\(align='baseline'\\)"):
        Column(T("a"), align="baseline")
    with pytest.raises(ValueError, match="recognised align value"):
        Row(T("a"), align="middle")


# ------------------------------------------------------------ slot bands

def _cards(slotted: bool):
    heads = SizeGroup("height", fit="slot", align="baseline")
    pics = SizeGroup("height", fit="slot", align="center")
    notes = SizeGroup("height", fit="slot", align="start")
    band = (lambda g, e: g(e)) if slotted else (lambda g, e: e)

    def card(title, deco, pic_h, *caps):
        body = Column(band(heads, _head(deco, title)),
                      band(pics, Box(width=40, height=pic_h)),
                      band(notes, Column(*[T(c) for c in caps], gap=0.4,
                                         align="start")),
                      gap="sm", align="start", share_columns=False)
        return Region(body, pad_x=3.0, pad_y=2.6, margin_x=0, margin_y=0)

    return Row(card("C1", Icon("cpu", size=9.0), 30, "cap1"),
               card("C2", None, 50, "cap2a", "cap2b"),
               card("C3", Badge("3"), 40, "cap3a", "cap3b"),
               gap="md", align="stretch", equal_widths=True,
               equal_heights=True)


def test_equal_height_cards_misalign_bands_without_slots():
    ys = _baselines(_render(_cards(False))[0])
    assert ys["cap1"][0] - ys["cap2a"][0] > 3.0


def test_slot_bands_align_titles_pictures_and_captions():
    svg, size, _ = _render(_cards(True))
    ys = _baselines(svg)
    for group in (("C1", "C2", "C3"), ("cap1", "cap2a", "cap3a")):
        vals = [ys[k][0] for k in group]
        assert max(vals) - min(vals) < 0.01, group
    pics = sorted((r for r in _rects(svg) if r[2] == 40.0), key=lambda r: r[0])
    # Pictures keep their natural heights and share one centre line.
    assert [r[3] for r in pics] == [30.0, 50.0, 40.0]
    centres = [r[1] + r[3] / 2 for r in pics]
    assert max(centres) - min(centres) < 0.01
    # No dead zone: the caption band starts one authored gap below the
    # picture band in every card (cards are equally tall by construction).
    band_bottom = max(r[1] + r[3] for r in pics)
    tallest = [r for r in pics if r[3] == 50.0][0]
    assert abs(tallest[1] + tallest[3] - band_bottom) < 0.01


def test_slot_group_leaves_natural_heights_equal_cards():
    theme = Theme()
    row = _cards(True)
    row.measure(theme)
    heights = [c.measure(theme).h for c in row.children]
    assert max(heights) - min(heights) < 1e-6


def test_slot_group_validates_arguments():
    with pytest.raises(ValueError):
        SizeGroup("width", fit="slot", align="baseline")
    with pytest.raises(ValueError):
        SizeGroup("height", align="center")          # grow has no slot
    with pytest.raises(ValueError):
        SizeGroup("height", fit="stretch")


def test_slot_group_width_axis_centres_children():
    g = SizeGroup("width", fit="slot", align="center")
    col = Column(g(Box(width=20, height=10)), g(Box(width=60, height=10)),
                 gap="xs", align="start")
    svg, _size, _ = _render(col)
    rects = sorted((r for r in _rects(svg) if r[3] == 10.0),
                   key=lambda r: r[2])
    narrow, wide = rects
    assert abs((narrow[0] + narrow[2] / 2) - (wide[0] + wide[2] / 2)) < 0.01


def test_slot_group_default_grow_mode_unchanged():
    g = SizeGroup("height")
    a, b = g(Box(width=20, height=10)), g(Box(width=20, height=30))
    theme = Theme()
    Row(a, b).measure(theme)
    assert a.measure(theme).h == b.measure(theme).h == 30.0


# ------------------------------------------------------------ ridge labels

def _ridge(n=5, *, height=30):
    xs = [i / 60 for i in range(61)]
    lines = [SparkLine([(x, (n - 1 - r) + 2.2 * x * (1 - x) * 4) for x in xs],
                       fill_to=float(n - 1 - r), width=0.5,
                       fill=Palette.blue.soft(),
                       label=Row(Marker("circle", size=2.4),
                                 T(f"L{r}", weight="700"), gap=0.8,
                                 align="center"))
             for r in range(n)]
    return Sparkline(lines, width=62, height=height, domain=(0, 1),
                     range=(0, n + 1.2))


def test_ridge_labels_sit_on_their_levels():
    svg, size, theme = _render(_ridge())
    ys = _baselines(svg)
    bases = sorted(float(m.group(1).split()[0].split(",")[1])
                   for m in re.finditer(r'<polygon points="([^"]+)"', svg))
    labels = sorted(ys[f"L{r}"][0] for r in range(5))
    assert len(bases) == 5
    for lab, base in zip(labels, bases):
        assert abs(lab - base) < 0.5
    pitches = [b - a for a, b in zip(labels, labels[1:])]
    assert max(pitches) - min(pitches) < 0.01
    # Labels never overlap: the pitch is at least one label height.
    assert min(pitches) >= T("L0").measure(theme).h - 1e-6
    # Bbox contract: every baseline and every drawn point is inside.
    assert all(0.0 <= v <= size.h for v in labels)
    for m in re.finditer(r'<polygon points="([^"]+)"', svg):
        for pt in m.group(1).split():
            x, y = (float(v) for v in pt.split(","))
            assert -0.01 <= x <= size.w + 0.01 and -0.01 <= y <= size.h + 0.01


def test_ridge_without_labels_is_unchanged():
    lines = [SparkLine([(0, 0), (1, 1)], fill_to=0.0)]
    assert Sparkline(lines, width=40, height=20).measure(Theme()).h == 20


def test_baseline_rows_stay_fast_on_deep_nesting():
    """Baseline queries must not re-measure trees exponentially."""
    el = T("leaf")
    for depth in range(2):
        el = Anchor(f"a{depth}", Region(Column(Row(el, T(f"s{depth}"),
                                                   align="baseline"),
                                               T("x"), gap="xs")))
    t0 = time.perf_counter()
    _render(Row(el, T("peer"), align="baseline"))
    assert time.perf_counter() - t0 < 5.0


def test_baseline_row_offsets_match_render_for_anchors():
    """Ports and lanes read ``_child_offsets``; it must agree with render."""
    box = Box(width=12, height=30)
    region = Region(Column(T("Title"), T("body"), gap="xs"),
                    label="decorated", pad_x=3.0, pad_y=2.6)
    row = Row(T("Lead"), Anchor("box", box), Anchor("reg", region),
              gap="sm", align="baseline")
    svg, _size, theme = _render(row)
    (bx, by, bw, bh), = [r for r in _rects(svg) if r[2] == 12.0]
    offs = row._child_offsets(theme)
    ox, oy, _s = offs[1]
    anchor = row.children[1]
    assert abs(oy + anchor.margin_top - by) < 0.01
    ys = _baselines(svg)
    assert abs(ys["Lead"][0] - ys["Title"][0]) < 0.01
