"""Column(align="stretch") must measure exactly its widest child.

Regression: a stretch column of icon + text Rows of differing widths
used to overshoot its widest child by up to half the narrowest child's
centring slack. ``_maybe_stretch_widths`` inflates every Row to the
widest sibling; an inflated Row centres its content between side slots;
the cross-extent union then aligned children on *content* landmarks,
double-counting that slack (left = max content offset, right = max
outer-minus-offset, taken from different children). Since ``Card``
defaults to a stretch body column, every multi-row card in a paper
inherited the phantom width.
"""
from __future__ import annotations

from sciviz import Card, Column, Icon, Row, Text, TextBlock, Theme


def _port_row(name: str, sub: str | None = None) -> Row:
    lines = [Text(name, size="tiny", weight="700")]
    if sub:
        lines.append(TextBlock(sub, size="micro", max_width=96.0))
    return Row(
        Icon("box", size=10),
        Column(*lines, gap="none", align="start"),
        gap="xs", align="center",
    )


def test_stretch_column_width_equals_widest_child():
    theme = Theme()
    rows = [
        _port_row("candidate_schema"),
        _port_row("validate"),
        _port_row("evaluate", "objectives, diagnostics, cost, receipt"),
        _port_row("domain prompt (optional)", "frozen ablation arm"),
    ]
    widest = max(r.measure(theme).w for r in rows)

    fresh = [
        _port_row("candidate_schema"),
        _port_row("validate"),
        _port_row("evaluate", "objectives, diagnostics, cost, receipt"),
        _port_row("domain prompt (optional)", "frozen ablation arm"),
    ]
    col = Column(*fresh, gap="xs", align="stretch")
    got = col.measure(theme).w
    assert got <= widest + 0.5, (
        f"stretch column measures {got}, widest child is {widest}")


def test_card_with_stretch_body_tracks_widest_row():
    theme = Theme()
    rows = [
        _port_row("candidate_schema"),
        _port_row("validate"),
        _port_row("evaluate", "objectives, diagnostics, cost, receipt"),
    ]
    widest = max(r.measure(theme).w for r in rows)
    card = Card(
        Text("Ports", color="white", size="tiny", weight="700"),
        Column(
            _port_row("candidate_schema"),
            _port_row("validate"),
            _port_row("evaluate", "objectives, diagnostics, cost, receipt"),
            gap="xs", align="stretch",
        ),
        role=None or __import__("sciviz").Palette.blue,
    )
    got = card.measure(theme).w
    # Card adds only its own padding around the widest row.
    assert got <= widest + 4 * theme.unit, (
        f"card measures {got} around widest row {widest}")
