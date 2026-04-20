"""Behavioural tests for :class:`sciviz.Banner`.

Key invariant: a ``Banner(body, above=hdr, below=ftr)`` reports
``content_bbox == body.content_bbox`` (translated into its own frame),
so a sibling :class:`Row` / :class:`Column` that centers on content
bboxes aligns on the *body* midline. This is what allows a header to
float above a row without shifting the row vertically relative to its
uncaptioned siblings.
"""
from __future__ import annotations

import math

from sciviz import Banner, Box, Column, DEFAULT_THEME, Row, Text


def _bbox(e):
    return e.measure(DEFAULT_THEME)


def _cbox(e):
    return e.content_bbox(DEFAULT_THEME)


def test_banner_no_header_no_footer_is_transparent():
    body = Box("body", width=60, height=40)
    b = Banner(body)
    assert math.isclose(_bbox(b).w, _bbox(body).w)
    assert math.isclose(_bbox(b).h, _bbox(body).h)


def test_banner_stacks_above_body_below():
    body = Box("body", width=60, height=40)
    hdr = Text("title")
    ftr = Text("sub")
    b = Banner(body, above=hdr, below=ftr, gap="sm")
    bb = _bbox(b)
    assert bb.h > _bbox(body).h  # header + footer add height
    assert bb.w >= _bbox(body).w  # width = max(parts)


def test_banner_content_bbox_excludes_header_and_footer():
    body = Box("body", width=60, height=40)
    hdr = Text("title")
    ftr = Text("sub")
    b = Banner(body, above=hdr, below=ftr)
    _, _, cw, ch = _cbox(b)
    bx, by, bw, bh = _cbox(body)
    # Body's content bbox is its full measure (default), so Banner's
    # content bbox width/height must match the body's.
    assert math.isclose(cw, bw)
    assert math.isclose(ch, bh)


def test_banner_aligns_siblings_on_body_midline_in_row():
    """A Banner-wrapped body sits in a Row next to a plain sibling: the
    sibling's vertical center should land on the body's midline, not on
    the banner-plus-header joint midline."""
    body = Box("wide body", width=80, height=60)
    hdr = Text("header")
    banner = Banner(body, above=hdr)

    sibling = Box("side", width=40, height=30)

    # Manually compute what a content-aware Row would do:
    # Row height = max(banner content bbox height, sibling content bbox
    # height) shifted by the header-reserved vertical offset. The
    # banner's content bbox y0 equals the header + gap reservation, so
    # when Row centers the sibling on the body midline, the sibling's
    # center lines up with body's center (not banner's overall center).
    row = Row(banner, sibling, align="center")
    row_h = _bbox(row).h

    # Row height must at least accommodate the banner (taller of the two).
    assert math.isclose(row_h, _bbox(banner).h)

    # Sibling should render centered on body midline. The row's content
    # bbox is union of children's content bboxes; we assert that the
    # banner's content bbox y-center equals the sibling's y-center after
    # placement. We verify indirectly via the banner.content_bbox y
    # midline in the banner's local frame.
    _bx, by, _bw, bh = _cbox(banner)
    body_y_mid = by + bh / 2
    # The body's intrinsic y-mid in the banner frame equals above.h +
    # gap + body.h/2. The banner's content bbox should reflect exactly
    # that midline.
    hdr_h = _bbox(hdr).h
    gap_px = DEFAULT_THEME.gap_px("sm")
    expected = hdr_h + gap_px + _bbox(body).h / 2
    assert math.isclose(body_y_mid, expected, abs_tol=0.5)


def test_banner_in_public_api():
    import sciviz
    assert "Banner" in sciviz.__all__
    assert sciviz.Banner is Banner
