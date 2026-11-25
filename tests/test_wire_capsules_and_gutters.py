"""Capsule captions, chip padding, equal painted widths, gutter
justification and paired wall tabs.

* ``Connect(label_frame="capsule")`` (or ``Theme.connector_label_frame``)
  sets every caption line as its own pill: the measured box holds the
  pills, the pills are never turned or re-wrapped, and the default stays
  a plain caption.
* ``Theme.chip_pad_x`` / ``chip_pad_y`` size a Chip and a capsule alike.
* ``Row(equal_widths="painted")`` equalises the PAINTED faces of its children,
  so a child carrying a flow lane is not painted narrower than its
  lane-less sisters; ``justify="between"`` sends a stretch surplus into
  the gutters instead of the slots.
* ``Region(tabs={"top": (start, end)})`` sets one tab at each end of a
  wall.
"""
from __future__ import annotations

import re

from sciviz import (Anchor, Box, Chip, Column, Connect, Diagram, Region,
                    Row, Text, Theme)
from sciviz.auto.labels import (capsule_geometry, caption_fit,
                                measure_label, rotated_caption)
from sciviz.core import Canvas


FILL, EDGE = "#f6d5e0", "#d98ca8"


def test_capsule_caption_measures_one_pill_per_line():
    theme = Theme()
    plain = measure_label("count\nsize", theme, "small")
    pills = measure_label("count\nsize", theme, "small", frame="capsule")
    pad_x, pill_h, gap = capsule_geometry(theme, "small")
    assert pills.frame == "capsule" and plain.frame == "none"
    assert abs(pills.width - (plain.width + 2 * pad_x)) < 1e-6
    assert abs(pills.height - (2 * pill_h + gap)) < 1e-6


def test_capsule_caption_is_never_turned_or_rewrapped():
    theme = Theme()
    fit = caption_fit("item count", theme, "small", src_side="right",
                      dst_side="left", neighbour_extent=10.0,
                      frame="capsule")
    assert fit.upright and fit.label.text == "item count"
    assert rotated_caption(fit.label, 500.0, 3.0) is None
    assert fit.label.set_to(5.0) is fit.label


def test_capsule_geometry_matches_chip_and_follows_theme_padding():
    base = Theme()
    tight = base.with_overrides(chip_pad_x=0.3, chip_pad_y=0.1)
    for theme in (base, tight):
        chip = Chip("abc", text_size="small").measure(theme)
        _pad_x, pill_h, _gap = capsule_geometry(theme, "small")
        assert abs(chip.h - pill_h) < 1e-6
    assert (Chip("abc").measure(tight).w < Chip("abc").measure(base).w)
    # defaults unchanged
    assert base.chip_pad_x == 0.72 and base.chip_pad_y == 0.36


def _wired(**connect_kw) -> str:
    theme = Theme().with_overrides(label_capsule_fill=FILL,
                                   label_capsule_stroke=EDGE)
    body = Column(
        Row(Anchor("a", Box("source")), Anchor("b", Box("sink")), gap=60),
        Connect("a", "b", src_side="right", dst_side="left",
                label="count\nsize", **connect_kw),
        gap="sm")
    return Diagram.for_paper(body, theme=theme).render()


def test_connect_capsule_frame_draws_pills_and_default_stays_plain():
    svg = _wired(label_frame="capsule")
    pills = re.findall(rf'<rect [^>]*fill="{FILL}"[^>]*>', svg)
    assert len(pills) == 2, svg
    assert all('rx="' in p and f'stroke="{EDGE}"' in p for p in pills)
    assert FILL not in _wired()


def test_theme_frame_applies_to_every_connector():
    theme = Theme().with_overrides(connector_label_frame="capsule",
                                   label_capsule_fill=FILL)
    body = Column(
        Row(Anchor("a", Box("source")), Anchor("b", Box("sink")), gap=60),
        Connect("a", "b", src_side="right", dst_side="left", label="count"),
        gap="sm")
    svg = Diagram.for_paper(body, theme=theme).render()
    assert len(re.findall(rf'fill="{FILL}"', svg)) == 1


def test_equal_widths_equalise_painted_faces_not_lanes():
    theme = Theme()
    laned = Anchor("x", Box("narrow"), margin_left=5.0)
    plain = Anchor("y", Box("a much wider box"))
    row = Row(laned, plain, equal_widths="painted", gap=4.0)
    row.measure(theme)
    faces = [laned.child.measure(theme).w, plain.child.measure(theme).w]
    assert abs(faces[0] - faces[1]) < 1e-6
    assert abs(laned.measure(theme).w - (faces[0] + 5.0)) < 1e-6


def test_equal_widths_between_sends_surplus_to_gutters():
    theme = Theme()

    def row(justify):
        a, b = Anchor("p", Box("one")), Anchor("q", Box("two three"))
        r = Row(a, b, equal_widths=True, gap=4.0, justify=justify)
        natural = r.measure(theme).w
        r.inflate_to(natural + 30.0, 0.0)
        r.measure(theme)
        return a, b, natural

    a, b, _ = row("between")
    assert abs(a.measure(theme).w - b.measure(theme).w) < 1e-6
    wide_a, _wide_b, _ = row("start")
    # "start" (historic) grows the slots; "between" keeps them
    assert a.measure(theme).w + 10.0 < wide_a.measure(theme).w
    canvas = Canvas()
    r = Row(Anchor("p", Box("one")), Anchor("q", Box("two three")),
            equal_widths=True, gap=4.0, justify="between")
    nat = r.measure(theme).w
    r.inflate_to(nat + 30.0, 0.0)
    assert abs(r.measure(theme).w - (nat + 30.0)) < 1e-6
    r.render(canvas, 0.0, 0.0, theme)


def test_region_wall_takes_a_start_and_an_end_tab():
    theme = Theme()
    one = Region(Text("body text"), tabs={"top": Text("name")})
    two = Region(Text("body text"),
                 tabs={"top": (Text("name"), Text("key entry"))})
    assert two.measure(theme).w > one.measure(theme).w
    canvas = Canvas()
    size = two.measure(theme)
    two.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    xs = {t: float(x) for x, t in re.findall(
        r'<text [^>]*x="([0-9.]+)"[^>]*>(name|key entry)</text>', svg)}
    assert set(xs) == {"name", "key entry"}
    assert xs["name"] < xs["key entry"]


def test_capsule_text_takes_theme_ink_unless_authored():
    ink = "#123456"
    theme = Theme().with_overrides(connector_label_frame="capsule",
                                   label_capsule_text=ink)

    def svg(**kw):
        body = Column(
            Row(Anchor("a", Box("source")), Anchor("b", Box("sink")),
                gap=60),
            Connect("a", "b", src_side="right", dst_side="left",
                    label="count", **kw),
            gap="sm")
        return Diagram.for_paper(body, theme=theme).render()

    assert re.search(rf'<text [^>]*fill="{ink}"[^>]*>count<', svg())
    assert not re.search(rf'<text [^>]*fill="{ink}"[^>]*>count<',
                         svg(label_color="#654321"))
