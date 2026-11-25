"""Balance captions never collide: two long pan names lengthen the beam."""
from sciviz import Balance, BalancePan, DEFAULT_THEME


def test_long_captions_widen_the_balance():
    theme = DEFAULT_THEME
    b = Balance(BalancePan("measured mass", 1.5), BalancePan("reference mass", 1.0),
                width=40, height=16, show_values=False)
    need = (theme.text_width("measured mass", "tiny")
            + theme.text_width("reference mass", "tiny"))
    assert b.measure(theme).w >= need


def test_short_captions_keep_the_authored_width():
    b = Balance(("a", 1.0), ("b", 2.0), width=76, height=40)
    assert b.measure(DEFAULT_THEME).w == 76
