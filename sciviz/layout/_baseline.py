"""First-baseline protocol shared by the layout containers.

An element that draws text may expose ``first_baseline(theme)``: the
distance, in px, from the TOP OF ITS ``content_bbox()`` to the baseline
of its first line of text, or ``None`` when it has no such line (icons,
markers, charts, rotated labels).  Measuring from the content box, not
the measured box, is deliberate: containers already align siblings on
their content boxes and keep the largest decoration reserve (a
``Region`` label, a badge, an ``Anchor`` wire lane) above them, so a
baseline counted from the outer box would count that reserve twice.

Each element computes its value from the same formula its ``render``
uses, so an aligned baseline is the drawn baseline, not an estimate.
:func:`first_baseline` is the one reader: it asks the element, and
passes through transparent single-child wrappers (``Anchor`` and the
like) that report their child's content box, translated, as their own.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

from ..core import Theme

#: Memo of one outermost baseline query.  A container asks each child
#: for its baseline and the child's own answer asks its children again
#: (through offsets and content boxes), so without it a nested card
#: re-derives the same leaf baselines once per ancestor.  Layout state
#: does not change within one query, so the memo is exact; it is
#: dropped when the outermost query returns.
_MEMO: ContextVar[Optional[dict]] = ContextVar("sciviz_baseline_memo",
                                               default=None)


def first_baseline(element, theme: Theme) -> Optional[float]:
    """The element's first text baseline below its content-box top.

    Returns ``None`` when the element exposes no baseline.  A wrapper
    without its own ``first_baseline`` that holds one ``child`` and
    reports that child's content box as its own (same size, translated;
    ``Anchor`` adds only margins) shares the child's baseline.
    """
    memo = _MEMO.get()
    if memo is None:
        token = _MEMO.set({})
        try:
            return first_baseline(element, theme)
        finally:
            _MEMO.reset(token)
    key = (id(element), id(theme))
    if key not in memo:
        memo[key] = _query(element, theme)
    return memo[key]


def _query(element, theme: Theme) -> Optional[float]:
    fn = getattr(element, "first_baseline", None)
    if callable(fn):
        return fn(theme)
    child = getattr(element, "child", None)
    if child is None or not hasattr(child, "content_bbox"):
        return None
    _x, _y, w, h = element.content_bbox(theme)
    _cx, _cy, cw, ch = child.content_bbox(theme)
    if abs(w - cw) > 1e-6 or abs(h - ch) > 1e-6:
        return None
    return first_baseline(child, theme)


def baseline_in_frame(element, theme: Theme, oy: float) -> Optional[float]:
    """Absolute baseline of ``element`` placed at vertical offset ``oy``.

    ``oy`` is where the element's measured box starts in the parent's
    frame; the result is in that frame, or ``None`` without a baseline.
    """
    b = first_baseline(element, theme)
    if b is None:
        return None
    return oy + element.content_bbox(theme)[1] + b
