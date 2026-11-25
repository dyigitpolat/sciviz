"""Wire margins keep what each end draws: head room where an arrowhead
lands, a visible stub at a plain tail (the rule Bus margins follow).
The floors are print floors, on only when ``Theme.min_space`` > 0."""
from sciviz import DEFAULT_THEME, Anchor, Box, Column, Connect, Row
from sciviz.connect._resolver import _FlowResolver


def _margins(head):
    theme = DEFAULT_THEME.with_overrides(unit=3.0, min_space=2.0)
    a, b = Anchor("a", Box("a")), Anchor("b", Box("b"))
    body = Column(Row(a, b, gap="md"),
                  Connect("a", "b", src_side="right", dst_side="left",
                          head=head))
    _FlowResolver(body)._apply_flow_margins(theme)
    return theme, a.margin_right, b.margin_left


def test_head_end_keeps_arrow_gutter_tail_keeps_stub():
    theme, tail, head = _margins(True)
    assert head >= theme.arrow_gutter_px() - 1e-9
    assert tail == max(theme.unit * 5 / 3, theme.min_space)
    assert tail < head


def test_both_heads_both_floored():
    theme, src, dst = _margins("both")
    assert min(src, dst) >= theme.arrow_gutter_px() - 1e-9


def test_default_unit_margin_unchanged():
    theme = DEFAULT_THEME
    assert theme.unit * 5 / 3 >= theme.arrow_gutter_px()


def test_no_floor_without_min_space():
    """With print floors off (the default) both ends compress
    proportionally, exactly as before floors existed."""
    theme = DEFAULT_THEME.with_overrides(unit=3.0)
    assert theme.min_space == 0.0 and not theme.print_floors
    a, b = Anchor("a", Box("a")), Anchor("b", Box("b"))
    body = Column(Row(a, b, gap="md"),
                  Connect("a", "b", src_side="right", dst_side="left",
                          head=True))
    _FlowResolver(body)._apply_flow_margins(theme)
    assert a.margin_right == b.margin_left == theme.unit * 5 / 3
