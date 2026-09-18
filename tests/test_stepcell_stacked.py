"""StepCell's stacked form: badge and visual in a top band, label beneath."""

from __future__ import annotations

from sciviz import DEFAULT_THEME, Diagram, Icon, Palette, StepCell

T = DEFAULT_THEME


def _cell(layout: str, **kw) -> StepCell:
    return StepCell("Derive search space", Icon("search", size=11),
                    index=2, role=Palette.indigo, layout=layout, **kw)


def test_stacked_is_narrower_and_taller_than_inline():
    inline, stacked = _cell("inline").measure(T), _cell("stacked").measure(T)
    assert stacked.w < inline.w
    assert stacked.h > inline.h


def test_label_width_caps_the_wrap_budget():
    wide = _cell("stacked", label_width=200.0).measure(T)
    narrow = _cell("stacked", label_width=30.0).measure(T)
    assert narrow.w < wide.w and narrow.h > wide.h


def test_stacked_renders_badge_and_label():
    svg = Diagram(_cell("stacked")).render(embed_fonts=False)
    assert ">2<" in svg and "Derive" in svg
