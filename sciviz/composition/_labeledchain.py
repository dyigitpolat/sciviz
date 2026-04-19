"""LabeledChain: horizontal items with auto-aligned top/bottom labels."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme
from ..layout import Row

class LabeledChain(Element):
    """Horizontal row of items with optional labels above and/or below.

    This primitive solves the recurring "three parallel rows that must
    share the same column centres" pattern (diffusion chains, labelled
    token strips, staged pipelines).  Each label is positioned so its
    horizontal centre lines up exactly with its item's centre, regardless
    of label width.

    Parameters
    ----------
    items : sequence of Element
        The main row of content.
    top_labels : sequence of Element, optional
        If provided, must have the same length as ``items``.  Each label
        is drawn above its item, centred on the item's column.
    bottom_labels : sequence of Element, optional
        Same as ``top_labels`` but rendered below the items row.
    arrow : str or Element, optional
        Either a short symbolic spec (``"->"``, ``"<-"``, ``"--"``) or an
        explicit :class:`Element` to draw between successive items.
        Default ``None`` (no connector).  String specs lower to
        :class:`Connector` with sensible defaults.
    gap : str or float
        Horizontal spacing between items (and between an item and its
        adjacent connector).
    label_gap : str or float
        Vertical spacing between the item row and each label row.
    """

    def __init__(self, items, *,
                 top_labels=None,
                 bottom_labels=None,
                 arrow=None,
                 gap: Union[str, float] = "md",
                 label_gap: Union[str, float] = "xs"):
        self.items = list(items)
        self.top_labels = list(top_labels) if top_labels is not None else None
        self.bottom_labels = list(bottom_labels) if bottom_labels is not None else None
        if self.top_labels is not None and len(self.top_labels) != len(self.items):
            raise ValueError(
                f"top_labels length {len(self.top_labels)} != items length "
                f"{len(self.items)}")
        if self.bottom_labels is not None and len(self.bottom_labels) != len(self.items):
            raise ValueError(
                f"bottom_labels length {len(self.bottom_labels)} != items length "
                f"{len(self.items)}")
        self.arrow = arrow
        self.gap = gap
        self.label_gap = label_gap

    # --- arrow lowering ----------------------------------------------------
    def _arrow_element(self) -> Optional[Element]:
        if self.arrow is None:
            return None
        if isinstance(self.arrow, Element):
            return self.arrow
        if isinstance(self.arrow, str):
            from ..elements import Connector
            style = self.arrow
            if style == "->":
                return Connector(direction="right", length=22)
            if style == "<-":
                return Connector(direction="left", length=22)
            if style == "--":
                return Connector(direction="right", length=22, head=False)
            raise ValueError(
                f"arrow string spec must be one of '->', '<-', '--'; got {style!r}")
        raise TypeError(f"arrow must be None, Element or str; got {type(self.arrow)}")

    def _items_row(self) -> Row:
        arrow = self._arrow_element()
        if arrow is None:
            kids = list(self.items)
        else:
            kids = []
            for i, it in enumerate(self.items):
                kids.append(it)
                if i < len(self.items) - 1:
                    kids.append(arrow)
        return Row(*kids, gap=self.gap, align="center")

    # --- geometry helpers --------------------------------------------------
    def _item_centres(self, theme: Theme):
        """Return the (x_centre, item_width) for each item when the row is
        rendered with its top-left at (0, 0).  Includes arrow separators."""
        row = self._items_row()
        row_bb = row.measure(theme)
        gap_px = theme.gap_px(self.gap)
        arrow = self._arrow_element()
        arrow_w = arrow.measure(theme).w if arrow is not None else 0.0
        item_sizes = [it.measure(theme) for it in self.items]
        row_h = max(s.h for s in item_sizes) if item_sizes else 0.0

        cx_list = []
        cur = 0.0
        for i, sz in enumerate(item_sizes):
            cx = cur + sz.w / 2
            cx_list.append(cx)
            cur += sz.w + gap_px
            if arrow is not None and i < len(item_sizes) - 1:
                cur += arrow_w + gap_px
        return cx_list, row_bb, row_h

    def _label_band(self, labels, theme: Theme):
        """Measure a label band by positioning each label centred on its
        item's x-centre.  Returns the band height."""
        if labels is None:
            return 0.0
        return max((lbl.measure(theme).h for lbl in labels), default=0.0)

    def measure(self, theme: Theme) -> BBox:
        _, row_bb, _ = self._item_centres(theme)
        top_h = self._label_band(self.top_labels, theme)
        bot_h = self._label_band(self.bottom_labels, theme)
        lg = theme.gap_px(self.label_gap)
        h = row_bb.h
        if self.top_labels is not None:
            h += top_h + lg
        if self.bottom_labels is not None:
            h += bot_h + lg
        return BBox(row_bb.w, h)

    def _render_label_band(self, labels, cx_list, canvas: Canvas, x: float,
                           y_top: float, theme: Theme, align_bottom: bool):
        """Render ``labels`` at rows whose centres line up with each item."""
        if labels is None:
            return
        band_h = max(lbl.measure(theme).h for lbl in labels)
        for lbl, cx in zip(labels, cx_list):
            lbb = lbl.measure(theme)
            lx = x + cx - lbb.w / 2
            if align_bottom:
                ly = y_top + (band_h - lbb.h)
            else:
                ly = y_top + (band_h - lbb.h)  # both bands bottom-aligned to
                # their band baseline, which looks better than top-align
            lbl.render(canvas, lx, ly, theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        cx_list, row_bb, _ = self._item_centres(theme)
        lg = theme.gap_px(self.label_gap)
        cur_y = y

        if self.top_labels is not None:
            top_h = max(lbl.measure(theme).h for lbl in self.top_labels)
            self._render_label_band(self.top_labels, cx_list, canvas, x, cur_y,
                                    theme, align_bottom=True)
            cur_y += top_h + lg

        self._items_row().render(canvas, x, cur_y, theme)
        cur_y += row_bb.h

        if self.bottom_labels is not None:
            cur_y += lg
            self._render_label_band(self.bottom_labels, cx_list, canvas, x, cur_y,
                                    theme, align_bottom=False)


