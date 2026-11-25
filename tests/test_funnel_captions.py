"""Funnel captions stay inside the funnel's measured box and never stack."""
from sciviz import DEFAULT_THEME, Funnel


def test_top_caption_stays_below_the_top_edge():
    f = Funnel([("pool", 8.0), ("kept", 1.0)], width=40, height=22,
               show_values=False)
    half = DEFAULT_THEME.text_height("tiny") / 2
    centres = f._label_centres(DEFAULT_THEME)
    assert centres[0] >= half - 1e-9
    assert f.measure(DEFAULT_THEME).h >= centres[-1] + half - 1e-9


def test_short_funnel_separates_its_captions():
    f = Funnel([("a", 4.0), ("b", 3.0), ("c", 2.0), ("d", 1.0)],
               width=30, height=12, show_values=False)
    line = DEFAULT_THEME.text_height("tiny")
    c = f._label_centres(DEFAULT_THEME)
    assert all(b - a >= line - 1e-9 for a, b in zip(c, c[1:]))
