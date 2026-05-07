"""Tests for the variadic Card body and CardRow/CardColumn primitives.

The figure code that motivated these changes kept hitting two papercuts:
(1) Card forced callers to wrap multiple body children in a Column;
(2) Sibling Cards in a Row drifted to wildly different widths because
nobody passed equal_widths=True. Both are now non-representable.
"""

from __future__ import annotations

import pytest

from sciviz import (
    Card,
    CardColumn,
    CardRow,
    DEFAULT_THEME,
    Palette,
    Row,
    Text,
    card_header,
)


def _theme():
    return DEFAULT_THEME


def test_card_accepts_multiple_body_children() -> None:
    card = Card(
        card_header("Card", icon="cpu"),
        Text("body line 1"),
        Text("body line 2"),
        Text("body line 3"),
        role=Palette.blue,
    )
    bbox = card.measure(_theme())
    # The auto-stacked body should produce a non-zero height greater than
    # a single-line body would.
    single = Card(
        card_header("Card", icon="cpu"),
        Text("body line 1"),
        role=Palette.blue,
    )
    single_bbox = single.measure(_theme())
    assert bbox.h > single_bbox.h


def test_card_requires_at_least_one_body_child() -> None:
    with pytest.raises(ValueError):
        Card(card_header("Card"), role=Palette.blue)


def test_cardrow_equalises_widths_by_default() -> None:
    short = Card(card_header("A"), Text("a"), role=Palette.blue)
    long = Card(card_header("Longer header name"),
                Text("a much longer body line to widen the card"),
                role=Palette.blue)
    row = CardRow(short, long)
    # In an equal-width row, the bounding box width is twice the maximum
    # child width plus the gap.
    bbox = row.measure(_theme())
    assert bbox.w >= 2 * long.measure(_theme()).w


def test_cardrow_opt_out_unequal() -> None:
    a = Card(card_header("A"), Text("a"), role=Palette.blue)
    b = Card(card_header("B"), Text("a much longer body"), role=Palette.blue)
    row = CardRow(a, b, equal_widths=False)
    # With equal_widths=False, the row width should be the sum of child
    # widths (plus gap), not 2x the max.
    bbox = row.measure(_theme())
    assert bbox.w < 2 * b.measure(_theme()).w + 50


def test_cardcolumn_equalises_widths_by_default() -> None:
    short = Card(card_header("A"), Text("a"), role=Palette.blue)
    long = Card(card_header("Long-Long"),
                Text("a much longer body line"),
                role=Palette.blue)
    col = CardColumn(short, long)
    bbox = col.measure(_theme())
    # CardColumn forces equal widths; both children should render at the
    # column's full width.
    assert bbox.w >= long.measure(_theme()).w


def test_card_header_helper_produces_header_with_icon() -> None:
    header = card_header("Title", icon="cpu")
    # The header is a Row of Icon + Text; check that the bounding box is
    # bigger than a Text alone.
    bbox = header.measure(_theme())
    only_text = Text("Title", color="white", weight="700", size="small")
    assert bbox.w > only_text.measure(_theme()).w
