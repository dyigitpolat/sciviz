"""A region's title on its border line, in the form of a fieldset legend (``tab_style="legend"``)."""
import re

import pytest

from sciviz import Box, Diagram, Region


def _svg(region):
    return Diagram(region).render(embed_fonts=False)


def _rects(svg):
    out = []
    for m in re.finditer(r"<rect\b[^>]*>", svg):
        tag = m.group(0)
        get = lambda k: re.search(rf'\b{k}="([^"]*)"', tag)          # noqa: E731
        out.append({k: (get(k).group(1) if get(k) else None)
                    for k in ("x", "y", "width", "height", "fill", "stroke", "rx")})
    return out


def _body():
    return Box(width=160.0, height=40.0, fill="#ffffff", stroke="none")


def _region(**kw):
    kw.setdefault("label", "Toolchain")
    kw.setdefault("label_style", "tab")
    kw.setdefault("color", "#808890")
    kw.setdefault("fill", "#eef0f2")
    kw.setdefault("dashed", False)
    return Region(_body(), **kw)


def test_default_tab_is_unchanged_by_the_new_keywords():
    assert _svg(_region()) == _svg(_region(tab_style="plate", tab_inset=None, tab_pad=None))


def test_legend_draws_no_plate_and_interrupts_the_wall_alone():
    plate, legend = _svg(_region(tab_outline=False)), _svg(_region(tab_style="legend"))
    assert "Toolchain" in legend
    # the plate form draws one rounded plate as high as the label; the legend form none
    plates = [r for r in _rects(plate) if r["rx"] and float(r["height"]) > 6.0 and r["fill"] != "#eef0f2"]
    assert plates
    gaps = [r for r in _rects(legend) if r["stroke"] in (None, "none") and r["x"] and float(r["height"]) < 4.0]
    assert len(gaps) == 2                                          # the outer and the inner half of the gap
    outer, inner = gaps
    assert inner["fill"].lower() == "#eef0f2"                      # the region's ground runs on under its title
    assert outer["fill"].lower() != "#eef0f2"                      # the page colour outside the wall
    assert float(outer["x"]) == float(inner["x"]) and float(outer["width"]) == float(inner["width"])
    assert float(outer["y"]) + float(outer["height"]) == pytest.approx(float(inner["y"]))   # they meet on the wall
    # no plate to hold: the legend reserves its capitals alone, so it is lower than the plate form
    height = lambda svg: float(re.search(r'viewBox="[\d.\-]+ [\d.\-]+ [\d.]+ ([\d.]+)"', svg).group(1))   # noqa: E731
    assert height(legend) < height(plate)


def test_wall_offsets_report_the_half_title_outside_the_wall():
    from sciviz import DEFAULT_THEME
    plain = Region(_body(), color="#808890", dashed=False, margin_y=0.0)
    assert plain.wall_offsets(DEFAULT_THEME) == (0.0, 0.0)
    top, bot = _region(tab_style="legend", margin_y=0.0).wall_offsets(DEFAULT_THEME)
    assert bot == 0.0 and top == pytest.approx(0.38 * DEFAULT_THEME.size_px("label"))


def test_legend_title_takes_less_height_than_a_label_row_inside():
    from sciviz import Column, Text
    inside = Diagram(Region(Column(Text("Toolchain", size="label", weight="700"), _body(), gap="xs"),
                            color="#808890", dashed=False)).render(embed_fonts=False)
    on_wall = _svg(_region(tab_style="legend"))
    height = lambda svg: float(re.search(r'viewBox="[\d.\-]+ [\d.\-]+ [\d.]+ ([\d.]+)"', svg).group(1))   # noqa: E731
    assert height(on_wall) < height(inside)


def test_stated_position_and_pad():
    def gap(**kw):
        r = [r for r in _rects(_svg(_region(tab_style="legend", **kw)))
             if r["stroke"] in (None, "none") and r["x"] and float(r["height"]) < 4.0][0]
        return float(r["x"]), float(r["width"])
    x_auto, w_auto = gap()
    x_10, _ = gap(tab_inset=10.0)
    x_20, _ = gap(tab_inset=20.0)
    assert x_20 - x_10 == pytest.approx(10.0)                      # the inset moves the title along its wall
    _, w_wide = gap(tab_pad=6.0)
    _, w_tight = gap(tab_pad=1.0)
    assert w_wide - w_tight == pytest.approx(10.0)                 # the pad on each side of the label
    assert w_auto > 0 and x_auto > 0


def test_legend_on_the_bottom_wall_and_refusals():
    svg = _svg(_region(tab_style="legend", label_position="bottom"))
    gaps = [r for r in _rects(svg) if r["stroke"] in (None, "none") and r["x"] and float(r["height"]) < 4.0]
    assert len(gaps) == 2
    with pytest.raises(ValueError):
        _region(tab_style="pill")
    with pytest.raises(ValueError):
        _region(tab_inset=-1.0)
    with pytest.raises(ValueError):
        _region(tab_pad=-0.5)
