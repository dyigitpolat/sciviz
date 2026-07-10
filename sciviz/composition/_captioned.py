"""Captioned: numbered / titled decoration stacked above a child."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme
from ..elements import Text
from ._badge import Badge

class Captioned(Element):
    """Wrap a child with a small vertical decoration above it.

    One of two kinds of decoration is supported, chosen by which
    keyword you pass:

    * ``number="1"`` (optionally with ``number_role=Palette.alert``) draws a
      :class:`Badge` above the child -- the canonical "numbered panel
      header" pattern (panel markers in a multi-variant figure).
    * ``title="FORWARD  (fixed)"`` (optionally with ``title_color=...``) draws
      a short bold :class:`Text` above the child -- the canonical
      "section kicker" pattern.

    Exactly one decoration is rendered; if you pass neither, ``Captioned``
    returns the child's extent unchanged so the wrapper is a no-op.

    Parameters
    ----------
    child : Element
        The body to decorate.
    number : str, optional
        A short badge label (typically "1", "2", "a", ...).
    number_role : ColorRef or str, optional
        Badge colour.  Defaults to theme ``info`` if omitted.
    number_size : float
        Badge diameter in pixels (default 24).
    title : str, optional
        A short bold kicker drawn above the child.
    title_color : ColorRef or str, optional
        Colour for the kicker.  Defaults to theme ``text``.
    title_size : str
        Theme size token for the kicker (default ``"small"``).
    gap : str or float
        Vertical gap between decoration and child.
    align : str
        Horizontal alignment of the narrower of (decoration, child) within
        the wider one.  Default ``"center"``.
    """

    def __init__(self, child: Element, *,
                 decoration: Optional[Element] = None,
                 number: Optional[str] = None,
                 number_role=None,
                 number_size: float = 24.0,
                 title: Optional[str] = None,
                 title_color=None,
                 title_size: str = "small",
                 gap: Union[str, float] = "xs",
                 align: str = "center",
                 align_on: str = "outer",
                 placement: str = "top"):
        """
        ``align_on``: ``"outer"`` (default, back-compat) reports the full
        captioned bbox as the content axis. ``"child"`` reports only the
        wrapped child's bbox so sibling :class:`Row` / :class:`Column`
        containers align on the child's midline, ignoring the caption.
        """
        self.child = child
        if decoration is not None and not isinstance(decoration, Element):
            raise TypeError("Captioned.decoration must be an Element")
        if decoration is not None and (number is not None or title is not None):
            raise ValueError(
                "Captioned.decoration cannot be combined with number/title"
            )
        if placement not in ("top", "bottom", "left", "right"):
            raise ValueError(
                "Captioned.placement must be top/bottom/left/right"
            )
        self.decoration = decoration
        self.number = number
        self.number_role = number_role
        self.number_size = number_size
        self.title = title
        self.title_color = title_color
        self.title_size = title_size
        self.gap = gap
        self.align = align
        self.placement = placement
        if align_on not in ("outer", "child"):
            raise ValueError(
                f"align_on must be 'outer' or 'child'; got {align_on!r}")
        self.align_on = align_on

    def _decoration(self) -> Optional[Element]:
        if self.decoration is not None:
            return self.decoration
        if self.number is not None:
            role = self.number_role if self.number_role is not None else "info"
            return Badge(self.number, color=role, size=self.number_size,
                         text_size="small")
        if self.title is not None:
            color = self.title_color if self.title_color is not None else "text"
            return Text(self.title, size=self.title_size, color=color,
                        weight="700")
        return None

    def measure(self, theme: Theme) -> BBox:
        d = self._decoration()
        if d is None:
            return self.child.measure(theme)
        d_bb = d.measure(theme)
        c_bb = self.child.measure(theme)
        gap_px = theme.gap_px(self.gap)
        if self.placement in ("top", "bottom"):
            return BBox(max(d_bb.w, c_bb.w), d_bb.h + gap_px + c_bb.h)
        return BBox(d_bb.w + gap_px + c_bb.w, max(d_bb.h, c_bb.h))

    def _offsets(self, theme: Theme):
        """Return decoration/child offsets inside the measured frame."""
        d = self._decoration()
        assert d is not None
        size = self.measure(theme)
        d_bb = d.measure(theme)
        c_bb = self.child.measure(theme)
        gap_px = theme.gap_px(self.gap)
        if self.placement == "top":
            d_pos = (_offset_like(self.align, size.w, d_bb.w), 0.0)
            c_pos = (_offset_like(self.align, size.w, c_bb.w),
                     d_bb.h + gap_px)
        elif self.placement == "bottom":
            c_pos = (_offset_like(self.align, size.w, c_bb.w), 0.0)
            d_pos = (_offset_like(self.align, size.w, d_bb.w),
                     c_bb.h + gap_px)
        elif self.placement == "left":
            d_pos = (0.0, _offset_like(self.align, size.h, d_bb.h))
            c_pos = (d_bb.w + gap_px,
                     _offset_like(self.align, size.h, c_bb.h))
        else:
            c_pos = (0.0, _offset_like(self.align, size.h, c_bb.h))
            d_pos = (c_bb.w + gap_px,
                     _offset_like(self.align, size.h, d_bb.h))
        return d_pos, c_pos

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        d = self._decoration()
        if d is None:
            self.child.render(canvas, x, y, theme)
            return
        d_pos, c_pos = self._offsets(theme)
        d.render(canvas, x + d_pos[0], y + d_pos[1], theme)
        self.child.render(canvas, x + c_pos[0], y + c_pos[1], theme)

    def content_bbox(self, theme: Theme):
        """When ``align_on="child"``, report only the wrapped child's
        bbox so sibling :class:`Row` / :class:`Column` containers align
        on the child's midline and the caption floats above without
        affecting cross-sibling alignment.
        """
        if self.align_on != "child":
            b = self.measure(theme)
            return (0.0, 0.0, b.w, b.h)
        d = self._decoration()
        if d is None:
            return self.child.content_bbox(theme)
        _d_pos, c_pos = self._offsets(theme)
        cx, cy, cw, ch = self.child.content_bbox(theme)
        return (c_pos[0] + cx, c_pos[1] + cy, cw, ch)

    # Captioned is a transparent decoration for sibling-aware layout.  A
    # title must not hide a Grid/Row's shared-column contract from Column or
    # AlignedStack; otherwise two titled panels drift even though their
    # underlying semantic columns correspond exactly.
    def _shared_column_widths(self, theme: Theme):
        probe = getattr(self.child, "_shared_column_widths", None)
        return list(probe(theme)) if probe is not None else []

    def _apply_shared_columns(self, widths) -> None:
        apply = getattr(self.child, "_apply_shared_columns", None)
        if apply is not None:
            apply(widths)

    def _stretch_visible_to_slots(self, widths) -> None:
        stretch = getattr(self.child, "_stretch_visible_to_slots", None)
        if stretch is not None:
            stretch(widths)


def _offset_like(align: str, outer_w: float, inner_w: float) -> float:
    if align == "start":
        return 0.0
    if align == "end":
        return outer_w - inner_w
    return (outer_w - inner_w) / 2
