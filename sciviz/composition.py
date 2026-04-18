"""Higher-level composition primitives.

These eliminate the most common patterns I kept writing manually:

* :class:`Inline`   -- baseline-aligned mixed text/math, no manual Spacers.
* :class:`Card`     -- title + body card with semantic tone.
* :class:`Section`  -- inline-label + math + body block (formula card).
* :class:`KeyValue` -- two-column key-value table (auto-aligns).
* :class:`Bullets`  -- list with consistent bullet/dash markers.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from .core import Element, BBox, Canvas, Theme
from .layout import Row, Column, Spacer
from .elements import Text, TextBlock


# ---------------------------------------------------------------------------
# Inline -- baseline-aligned heterogeneous text/math/etc.
# ---------------------------------------------------------------------------

class Inline(Element):
    """Lay out a sequence of text, math and small elements on a shared baseline.

    Replaces the ``Row(Text(...), Spacer(4, 0), Math(...), Spacer(4, 0), ...)``
    boilerplate with a single declarative call.  String children become
    :class:`Text` automatically; ``$...$`` strings become :class:`Math`.

    Parameters
    ----------
    *parts : Element or str
        Sequence to lay out.  Strings beginning and ending with ``$`` become
        :class:`Math`; other strings become :class:`Text`.
    size : str or float
        Default text/math size for string children.
    color : str
        Default text colour.
    weight : str
        Default text weight for string children.
    gap : str or float
        Whitespace between successive children (default ``"sm"`` ~ a wordspace).
    """

    def __init__(self, *parts, size="label", color="text",
                 weight="normal", gap="sm"):
        self.parts = list(parts)
        self.size = size
        self.color = color
        self.weight = weight
        self.gap = gap

    def _coerce(self, p):
        if isinstance(p, Element):
            return p
        if isinstance(p, str):
            s = p.strip()
            if len(s) >= 2 and s.startswith("$") and s.endswith("$"):
                from .math import Math
                return Math(s, size=self.size, color=self.color)
            return Text(p, size=self.size, color=self.color, weight=self.weight)
        raise TypeError(f"Inline parts must be Element or str; got {type(p)}")

    def _children(self):
        return [self._coerce(p) for p in self.parts]

    def measure(self, theme: Theme) -> BBox:
        kids = self._children()
        if not kids:
            return BBox(0, 0)
        sizes = [c.measure(theme) for c in kids]
        g = theme.gap_px(self.gap)
        w = sum(s.w for s in sizes) + g * (len(sizes) - 1)
        h = max(s.h for s in sizes)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        kids = self._children()
        if not kids:
            return
        sizes = [c.measure(theme) for c in kids]
        H = max(s.h for s in sizes)
        g = theme.gap_px(self.gap)
        cx = x
        for child, sz in zip(kids, sizes):
            cy = y + (H - sz.h) / 2
            child.render(canvas, cx, cy, theme)
            cx += sz.w + g


# ---------------------------------------------------------------------------
# Card -- title + body with semantic tone
# ---------------------------------------------------------------------------

class Card(Element):
    """Header + body block.  Replaces the common ``Column(Text(title), body)``
    pattern.  The header uses the role's ink colour; an optional accent rule
    sits below it.

    Parameters
    ----------
    title : str
        Header text.
    body : Element
        Anything composable.
    tone : str
        Color role (``"blue"``, ``"red"``, ``"green"``, ...) or ``"neutral"``.
        Determines header colour and the optional accent rule.
    rule : bool
        Draw a thin accent rule under the header.
    width : float, optional
        Constrain the card to a fixed width (body is centered).
    title_size : str
        Size token for the header (default ``"section"``).
    """

    def __init__(self, title: str, body: Element, *,
                 tone: str = "neutral",
                 rule: bool = False,
                 width: Optional[float] = None,
                 title_size: str = "section"):
        self.title = title
        self.body = body
        self.tone = tone
        self.rule = rule
        self.width = width
        self.title_size = title_size

    def _header(self, theme: Theme) -> Element:
        ink = theme.role(self.tone, "ink") if self.tone != "neutral" else theme.text
        return Text(self.title, size=self.title_size, color=ink, weight="700")

    def measure(self, theme: Theme) -> BBox:
        h = self._header(theme).measure(theme)
        b = self.body.measure(theme)
        gap = theme.unit * 0.6
        rule_h = 1.0 + theme.unit * 0.3 if self.rule else 0.0
        w = self.width if self.width is not None else max(h.w, b.w)
        return BBox(w, h.h + rule_h + gap + b.h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        size = self.measure(theme)
        header = self._header(theme)
        h = header.measure(theme)
        header.render(canvas, x, y, theme)
        cy = y + h.h
        if self.rule:
            cy += theme.unit * 0.15
            ink = theme.role(self.tone, "fill") if self.tone != "neutral" else theme.color_of("border")
            canvas.line(x, cy, x + size.w, cy,
                       stroke=ink, stroke_width=theme.hairline)
            cy += 1.0 + theme.unit * 0.15
        cy += theme.unit * 0.5
        # body x: centered if width was set, else left-aligned
        b = self.body.measure(theme)
        bx = x + (size.w - b.w) / 2 if self.width is not None else x
        self.body.render(canvas, bx, cy, theme)


# ---------------------------------------------------------------------------
# KeyValue -- two-column metadata block
# ---------------------------------------------------------------------------

class KeyValue(Element):
    """A two-column key/value table that auto-aligns its columns.

    Convenient for a metadata sidebar: ``KeyValue([("height", "$h$"),
    ("lookup I/O", "$O(h)$"), ("range scan", "$O(h + k/B)$")])``.

    Each value may be a string (auto-coerced to :class:`Text` or :class:`Math`)
    or any :class:`Element`.

    Parameters
    ----------
    items : list of (key, value)
    key_color : str
        Colour role for the key column (default muted).
    value_color : str
        Colour role for the value column (default text).
    gap_x, gap_y : str or float
    """

    def __init__(self, items, *,
                 key_color: str = "muted",
                 value_color: str = "text",
                 key_size: str = "small",
                 value_size: str = "small",
                 key_weight: str = "700",
                 gap_x="md", gap_y="xs"):
        self.items = list(items)
        self.key_color = key_color
        self.value_color = value_color
        self.key_size = key_size
        self.value_size = value_size
        self.key_weight = key_weight
        self.gap_x = gap_x
        self.gap_y = gap_y

    def _coerce(self, v, color, size):
        if isinstance(v, Element):
            return v
        s = str(v).strip()
        if len(s) >= 2 and s.startswith("$") and s.endswith("$"):
            from .math import Math
            return Math(s, size=size, color=color)
        return Text(s, size=size, color=color)

    def _build(self, theme):
        rows = []
        for k, v in self.items:
            key = self._coerce(k, self.key_color, self.key_size)
            # explicitly set key to the requested weight if it was a plain string
            if not isinstance(k, Element):
                key = Text(str(k), size=self.key_size,
                           color=self.key_color, weight=self.key_weight)
            val = self._coerce(v, self.value_color, self.value_size)
            rows.append((key, val))
        return rows

    def measure(self, theme: Theme) -> BBox:
        rows = self._build(theme)
        if not rows:
            return BBox(0, 0)
        ksizes = [k.measure(theme) for k, _ in rows]
        vsizes = [v.measure(theme) for _, v in rows]
        kw = max(s.w for s in ksizes)
        vw = max(s.w for s in vsizes)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        row_h = [max(k.h, v.h) for k, v in zip(ksizes, vsizes)]
        return BBox(kw + gx + vw, sum(row_h) + gy * (len(rows) - 1))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        rows = self._build(theme)
        ksizes = [k.measure(theme) for k, _ in rows]
        vsizes = [v.measure(theme) for _, v in rows]
        kw = max(s.w for s in ksizes)
        gx = theme.gap_px(self.gap_x)
        gy = theme.gap_px(self.gap_y)
        cy = y
        for (key, val), ksize, vsize in zip(rows, ksizes, vsizes):
            row_h = max(ksize.h, vsize.h)
            # baseline-align key and value vertically
            key.render(canvas, x + (kw - ksize.w), cy + (row_h - ksize.h) / 2, theme)
            val.render(canvas, x + kw + gx, cy + (row_h - vsize.h) / 2, theme)
            cy += row_h + gy


# ---------------------------------------------------------------------------
# Bullets -- list with consistent markers
# ---------------------------------------------------------------------------

class Bullets(Element):
    """Vertical list of items prefixed with a bullet/dash/number.

    Each item may be a string or an :class:`Element`.  The marker column is
    auto-sized so the body indent is consistent.
    """

    def __init__(self, items, *,
                 marker: str = "\u2022",
                 size: str = "label",
                 color: str = "text",
                 gap_y="xs",
                 numbered: bool = False):
        self.items = list(items)
        self.marker = marker
        self.size = size
        self.color = color
        self.gap_y = gap_y
        self.numbered = numbered

    def _children(self):
        out = []
        for i, it in enumerate(self.items):
            if self.numbered:
                m = Text(f"{i+1}.", size=self.size, color="muted",
                         weight="700")
            else:
                m = Text(self.marker, size=self.size, color="muted")
            if isinstance(it, Element):
                body = it
            else:
                body = TextBlock(str(it), size=self.size, color=self.color)
            out.append((m, body))
        return out

    def measure(self, theme: Theme) -> BBox:
        kids = self._children()
        if not kids:
            return BBox(0, 0)
        msizes = [m.measure(theme) for m, _ in kids]
        bsizes = [b.measure(theme) for _, b in kids]
        mw = max(s.w for s in msizes)
        bw = max(s.w for s in bsizes)
        gx = theme.unit * 0.6
        gy = theme.gap_px(self.gap_y)
        return BBox(mw + gx + bw,
                    sum(max(m.h, b.h) for m, b in zip(msizes, bsizes))
                    + gy * (len(kids) - 1))

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        kids = self._children()
        msizes = [m.measure(theme) for m, _ in kids]
        bsizes = [b.measure(theme) for _, b in kids]
        mw = max(s.w for s in msizes)
        gx = theme.unit * 0.6
        gy = theme.gap_px(self.gap_y)
        cy = y
        for (mark, body), ms, bs in zip(kids, msizes, bsizes):
            row_h = max(ms.h, bs.h)
            mark.render(canvas, x + (mw - ms.w), cy, theme)
            body.render(canvas, x + mw + gx, cy, theme)
            cy += row_h + gy


# ---------------------------------------------------------------------------
# Badge -- small filled circle with centred text (number, letter, or symbol)
# ---------------------------------------------------------------------------

class Badge(Element):
    """A small filled circle with centred text.

    Used for both purposes that turn up constantly in figures:

    * **Numbered/lettered markers** that link a panel to a table row
      (``Badge("1", color=Palette.alert)``).
    * **Inline mathematical operators** drawn as circles, like a residual
      add (``Badge("+")``) or a concatenation (``Badge("c")``).

    Parameters
    ----------
    label : str
        Text inside the badge.  Keep short -- 1-3 characters typically.
    color : ColorRef or str
        Fill colour.  Text colour is auto-chosen for contrast.
    size : float
        Diameter in pixels.
    text_size : str
        Theme size token for the label.
    text_weight : str
        Font weight for the label.
    bordered : bool
        If True, draw a thin stroke around the badge.
    """

    # Sentinel: "auto" means "pick a fill based on bordered-ness".
    # Bordered=True is the paper-style operator glyph (+, c, ×) -- drawn
    # as a ring with a dark glyph; so the interior should be the page
    # colour ("none" = transparent) rather than the info blue.
    _AUTO_COLOR = "__auto__"

    def __init__(self, label: str = "", *,
                 color = _AUTO_COLOR,
                 size: float = 18.0,
                 text_size: str = "small",
                 text_weight: str = "700",
                 bordered: bool = False,
                 stroke_color = None):
        self.label = str(label)
        self.color = color
        self.size = size
        self.text_size = text_size
        self.text_weight = text_weight
        self.bordered = bordered
        self.stroke_color = stroke_color

    def measure(self, theme: Theme) -> BBox:
        return BBox(self.size, self.size)

    def _resolved_fill(self, theme: Theme) -> str:
        if self.color is Badge._AUTO_COLOR:
            # No explicit colour: bordered => transparent paper interior,
            # un-bordered => classic info-blue fill.
            return "none" if self.bordered else theme.color_of("info")
        return theme.color_of(self.color)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        fill = self._resolved_fill(theme)
        cx = x + self.size / 2
        cy = y + self.size / 2
        stroke = "none"
        sw = 0.0
        if self.bordered:
            stroke = theme.color_of(self.stroke_color or "text")
            sw = theme.hairline
        canvas.circle(cx, cy, self.size / 2,
                     fill=fill, stroke=stroke, stroke_width=sw)
        if self.label:
            # For a transparent paper-style operator badge, the glyph
            # sits on the page background -- use the dark text colour
            # rather than "text_on(transparent)" which is undefined.
            if fill == "none":
                text_color = theme.color_of("text")
            else:
                text_color = theme.text_on(fill)
            canvas.text(cx, cy, self.label,
                       size=theme.size_px(self.text_size),
                       fill=text_color,
                       weight=self.text_weight,
                       anchor="middle", baseline="middle")


# ---------------------------------------------------------------------------
# Brace -- horizontal curly brace with optional label, used for grouping
# ---------------------------------------------------------------------------

class Brace(Element):
    """A horizontal curly brace with an optional label.

    Used to visually group a set of items above or below the brace.  Common
    in math figures (\\underbrace, \\overbrace) and in diagrams to show
    groupings like "Visual Tokens" or "Action Tokens".

    Parameters
    ----------
    span : float
        Pixel width spanned by the brace.
    label : str, optional
        Text label, placed below ("down") or above ("up") the brace.
    direction : str
        ``"down"`` (default, label below) or ``"up"`` (label above).
    color : ColorRef or str
        Stroke + label colour.
    height : float
        Vertical extent of the brace's curve.
    """

    def __init__(self, span: float, label: Optional[str] = None, *,
                 direction: str = "down",
                 color = "muted",
                 height: float = 6.0,
                 label_size: str = "small"):
        self.span = float(span)
        self.label = label
        self.direction = direction
        self.color = color
        self.height = float(height)
        self.label_size = label_size

    def measure(self, theme: Theme) -> BBox:
        h = self.height + 2
        if self.label:
            h += theme.text_height(self.label_size) + theme.unit * 0.4
        return BBox(self.span, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        col = theme.color_of(self.color)
        sz = theme.size_px(self.label_size)
        if self.direction == "down":
            # Brace points downward (label below).  Side endpoints sit at the
            # TOP of the brace region; the central tip drops below.
            top = y                              # endpoints level
            shoulder = y + self.height * 0.55    # where side curves meet horizontals
            tip = y + self.height + 3            # central tip drops past base
            mid = x + self.span / 2
            d = (
                f"M {x:.2f},{top:.2f} "
                f"Q {x:.2f},{shoulder:.2f} {x + 6:.2f},{shoulder:.2f} "
                f"L {mid - 6:.2f},{shoulder:.2f} "
                f"Q {mid:.2f},{shoulder:.2f} {mid:.2f},{tip:.2f} "
                f"Q {mid:.2f},{shoulder:.2f} {mid + 6:.2f},{shoulder:.2f} "
                f"L {x + self.span - 6:.2f},{shoulder:.2f} "
                f"Q {x + self.span:.2f},{shoulder:.2f} {x + self.span:.2f},{top:.2f}"
            )
            canvas.path(d, stroke=col, fill="none", stroke_width=theme.hairline)
            if self.label:
                canvas.text(mid, tip + sz + 2, self.label,
                           size=sz, fill=col, anchor="middle")
        else:  # "up"
            bot = y + self.height
            shoulder = y + self.height * 0.45
            tip = y - 3
            mid = x + self.span / 2
            d = (
                f"M {x:.2f},{bot:.2f} "
                f"Q {x:.2f},{shoulder:.2f} {x + 6:.2f},{shoulder:.2f} "
                f"L {mid - 6:.2f},{shoulder:.2f} "
                f"Q {mid:.2f},{shoulder:.2f} {mid:.2f},{tip:.2f} "
                f"Q {mid:.2f},{shoulder:.2f} {mid + 6:.2f},{shoulder:.2f} "
                f"L {x + self.span - 6:.2f},{shoulder:.2f} "
                f"Q {x + self.span:.2f},{shoulder:.2f} {x + self.span:.2f},{bot:.2f}"
            )
            canvas.path(d, stroke=col, fill="none", stroke_width=theme.hairline)
            if self.label:
                canvas.text(mid, tip - 6, self.label,
                           size=sz, fill=col, anchor="middle")


# ---------------------------------------------------------------------------
# Annotated -- overlay arbitrary drawing on top of a child element
# ---------------------------------------------------------------------------

class Annotated(Element):
    """Wrap a child and overlay arbitrary annotations after it renders.

    The escape hatch for visualisations the high-level API doesn't directly
    support: curved arrows between specific anchors, callouts, custom
    decoration.  The ``draw`` callback receives the raw canvas, the bbox
    coordinates, and the theme; you can draw anything you want with absolute
    coordinates relative to the bbox.

    Example
    -------
    >>> def overlay(canvas, x, y, w, h, theme):
    ...     canvas.path(f"M {x+10},{y+h} C ...", stroke="red")
    >>> Annotated(my_panel, draw=overlay)
    """

    def __init__(self, child: Element, *, draw=None,
                 inflate: tuple = (0, 0, 0, 0)):
        """
        ``inflate`` -- (left, top, right, bottom) pixels to extend the bbox
        beyond the child, useful when an annotation needs to extend outside
        the child's drawn area.
        """
        self.child = child
        self.draw = draw
        self.inflate = inflate

    def measure(self, theme: Theme) -> BBox:
        b = self.child.measure(theme)
        l, t, r, bt = self.inflate
        return BBox(b.w + l + r, b.h + t + bt)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        l, t, r, bt = self.inflate
        b = self.child.measure(theme)
        # render child offset by (l, t) so inflate gives space around it
        self.child.render(canvas, x + l, y + t, theme)
        if self.draw is not None:
            # callback gets the child's bbox in absolute coords
            self.draw(canvas, x + l, y + t, b.w, b.h, theme)


# ---------------------------------------------------------------------------
# Anchor + Flow + Flowed -- declarative curved arrows between named elements
# ---------------------------------------------------------------------------
import contextvars as _cv
# Stack of active registries.  Each Flowed pushes a fresh dict; Anchor
# registers itself in ALL active registries, so nested Flowed's anchors
# remain reachable from outer flows.
_anchor_stack: _cv.ContextVar = _cv.ContextVar("_anchor_stack", default=None)


class Anchor(Element):
    """Wrap a child and register its rendered bbox under a name.

    The author tags elements they want to draw flows between::

        Anchor("ae", encoder_box)

    A surrounding :class:`Flowed` then routes :class:`Flow` arrows between
    the named anchors.  The author writes no coordinates by hand.

    Anchors also carry per-side *margins* (default 0) that are added to
    the anchor's bbox in layout.  :class:`Flowed` automatically inflates
    these margins for flow-connected anchors during a pre-measure pass
    so every Flow has visible space for its arrow shaft.  The arrow
    endpoints remain at the *child's* boundary, not the padded bbox --
    registration records the child's true position.
    """

    def __init__(self, name: str, child: Element, *,
                 margin_left: float = 0.0,
                 margin_right: float = 0.0,
                 margin_top: float = 0.0,
                 margin_bottom: float = 0.0):
        self.name = name
        self.child = child
        self.margin_left = margin_left
        self.margin_right = margin_right
        self.margin_top = margin_top
        self.margin_bottom = margin_bottom

    def measure(self, theme: Theme) -> BBox:
        b = self.child.measure(theme)
        return BBox(b.w + self.margin_left + self.margin_right,
                    b.h + self.margin_top + self.margin_bottom)

    def content_bbox(self, theme: Theme):
        """The inner child bbox, excluding margins.  Layout containers use
        this to align siblings on their *content* box, not on the
        margin-inflated outer box -- so asymmetric flow-margin bumps
        don't shift the rendered child.

        When the child itself exposes a narrower content (e.g.
        ``StackedBoxes`` whose content_bbox is the FRONT face), inherit
        that so that Anchor doesn't undo the child's own content-vs-outer
        distinction.
        """
        child_cb = self.child.content_bbox(theme)
        cx, cy, cw, ch = child_cb
        return (self.margin_left + cx, self.margin_top + cy, cw, ch)

    def primary_anchor_bbox(self, theme: Theme):
        """Delegate to the child's primary anchor (if any), translated
        into our local frame; otherwise fall back to the child's content
        bbox.  This lets composites like ``Anchor(StackedBoxes(...))``
        expose the stack's FRONT FACE as the primary anchor, so Grid
        centres columns on the visible face rather than the silhouette.
        """
        pa = self.child.primary_anchor_bbox(theme)
        if pa is not None:
            px, py, pw, ph = pa
            return (self.margin_left + px, self.margin_top + py, pw, ph)
        return self.content_bbox(theme)

    def iter_primary_anchors(self, theme: Theme):
        out = []
        for px, py, pw, ph in self.child.iter_primary_anchors(theme):
            out.append((self.margin_left + px, self.margin_top + py, pw, ph))
        return out

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        b = self.child.measure(theme)
        child_x = x + self.margin_left
        child_y = y + self.margin_top
        # Register the CHILD's position, not the padded anchor bbox, so
        # flow endpoints land on the child's actual boundary.
        stack = _anchor_stack.get()
        if stack is not None:
            for reg in stack:
                reg[self.name] = (child_x, child_y, b.w, b.h)
        self.child.render(canvas, child_x, child_y, theme)

    def _bump_margin(self, side: str, amount: float) -> None:
        if side in ("left",):
            self.margin_left = max(self.margin_left, amount)
        elif side in ("right",):
            self.margin_right = max(self.margin_right, amount)
        elif side in ("top", "topleft", "topright"):
            self.margin_top = max(self.margin_top, amount)
        elif side in ("bottom", "bottomleft", "bottomright"):
            self.margin_bottom = max(self.margin_bottom, amount)


def _side_point(bbox, side: str):
    """Return (x, y) on a named side of an (x, y, w, h) bbox.

    Sides: ``top, bottom, left, right`` (midpoints) and the four corners
    ``topleft / topright / bottomleft / bottomright``.
    """
    x, y, w, h = bbox
    cx, cy = x + w / 2, y + h / 2
    return {
        "top":         (cx, y),
        "bottom":      (cx, y + h),
        "left":        (x, cy),
        "right":       (x + w, cy),
        "topleft":     (x, y),
        "topright":    (x + w, y),
        "bottomleft":  (x, y + h),
        "bottomright": (x + w, y + h),
    }[side]


def _side_point_frac(bbox, side: str, frac: float):
    """Point on ``side`` at relative position ``frac`` (0..1) along the
    edge.  For ``top``/``bottom`` edges, frac=0 is the left corner and
    frac=1 is the right corner.  For ``left``/``right`` edges, frac=0
    is the top corner.  A small inset keeps the tap off the exact
    corner.
    """
    x, y, w, h = bbox
    inset_px = min(4.0, w * 0.2, h * 0.2)
    frac = max(0.0, min(1.0, frac))
    if side in ("top", "bottom"):
        lo = x + inset_px
        hi = x + w - inset_px
        if hi <= lo:
            lo, hi = x, x + w
        px = lo + (hi - lo) * frac
        py = y if side == "top" else y + h
        return (px, py)
    if side in ("left", "right"):
        lo = y + inset_px
        hi = y + h - inset_px
        if hi <= lo:
            lo, hi = y, y + h
        py = lo + (hi - lo) * frac
        px = x if side == "left" else x + w
        return (px, py)
    return _side_point(bbox, side)


class Flow:
    """A curved arrow specification between two named anchors.

    Resolved by :class:`Flowed` after the child has rendered.  The author
    never touches pixel coordinates -- routing is computed from bbox sides.
    """

    def __init__(self, src: str, dst: str, *,
                 src_side: str = "auto",
                 dst_side: str = "auto",
                 color = "text",
                 label: Optional[str] = None,
                 dashed: bool = False,
                 curvature: float = 0.5,
                 detour: float = 24.0,
                 arrow: bool = True,
                 style: str = "orthogonal"):
        """
        ``src_side`` / ``dst_side`` -- which side of each bbox the flow
            attaches to.  Default ``"auto"`` picks the boundary side facing
            the other anchor: above/below/left/right.  Named sides:
            ``top/bottom/left/right`` (midpoints) and the four corners.

        ``curvature`` -- 0..1, how much the curve bows (0 = straight).
        ``detour``    -- pixels the curve bows beyond the larger of src/dst,
                         used when src and dst exit in the same direction.
        """
        self.src = src
        self.dst = dst
        self.src_side = src_side
        self.dst_side = dst_side
        self.color = color
        self.label = label
        self.dashed = dashed
        self.curvature = curvature
        self.detour = detour
        self.arrow = arrow
        self.style = style

    @staticmethod
    def _auto_side(self_bbox, other_bbox):
        """Return the side of ``self_bbox`` whose midpoint best faces other."""
        sx, sy, sw, sh = self_bbox
        ox, oy, ow, oh = other_bbox
        self_cx, self_cy = sx + sw / 2, sy + sh / 2
        other_cx, other_cy = ox + ow / 2, oy + oh / 2
        dx = other_cx - self_cx
        dy = other_cy - self_cy
        if abs(dx) > abs(dy):
            return "right" if dx > 0 else "left"
        return "bottom" if dy > 0 else "top"

    def _render(self, canvas: Canvas, theme: Theme, registry: dict):
        sb = registry.get(self.src)
        db = registry.get(self.dst)
        if sb is None or db is None:
            return
        src_side = self._auto_side(sb, db) if self.src_side == "auto" else self.src_side
        dst_side = self._auto_side(db, sb) if self.dst_side == "auto" else self.dst_side
        src_frac = getattr(self, "_share_src_frac", 0.5)
        dst_frac = getattr(self, "_share_dst_frac", 0.5)
        sx, sy = _side_point_frac(sb, src_side, src_frac)
        dx, dy = _side_point_frac(db, dst_side, dst_frac)

        col = theme.color_of(self.color)
        sw = theme.connector
        dash = "5,3" if self.dashed else None
        marker = (canvas.define_arrow_marker(
                      color=col, stroke_width=sw,
                      arrow_size=getattr(theme, "arrow_size", None),
                      name_hint="flow")
                  if self.arrow else None)

        # Orthogonal routing is delegated to the shared topological
        # planner (`sciviz.routing`).  The planner decides which region
        # boundaries *must* be crossed (the symmetric difference of the
        # two endpoints' region ancestors) and forbids the path from
        # entering any other region.  This replaces the ad-hoc vertical
        # / horizontal / mixed branches that used to live here.
        if self.style == "orthogonal":
            from . import routing as _rt

            tap = theme.unit * 2
            sb_x, sb_y, sb_w, sb_h = sb
            db_x, db_y, db_w, db_h = db

            # Raw anchor and region boxes.
            all_anchors = []
            all_regions = []
            for name, b in registry.items():
                bx, by, bw, bh = b
                if name.startswith("__region_"):
                    all_regions.append(_rt.Box(x=bx, y=by, w=bw, h=bh,
                                               name=name, kind="region"))
                else:
                    all_anchors.append(_rt.Box(x=bx, y=by, w=bw, h=bh,
                                               name=name, kind="anchor"))
            src_box = _rt.Box(x=sb_x, y=sb_y, w=sb_w, h=sb_h,
                              name=self.src, kind="anchor")
            dst_box = _rt.Box(x=db_x, y=db_y, w=db_w, h=db_h,
                              name=self.dst, kind="anchor")
            src_frac = getattr(self, "_share_src_frac", 0.5)
            dst_frac = getattr(self, "_share_dst_frac", 0.5)
            plan = _rt.plan_path(
                _rt.Endpoint(src_box, src_side, tap=tap,
                             tap_fraction=src_frac),
                _rt.Endpoint(dst_box, dst_side, tap=tap,
                             tap_fraction=dst_frac),
                anchors=all_anchors,
                regions=all_regions,
            )

            # Retain `anchor_obstacles` for label-placement collision
            # avoidance below.
            def _in(name):
                return name != self.src and name != self.dst
            anchor_obstacles = [b for name, b in registry.items()
                                if not name.startswith("__region_")
                                and _in(name)]
            # Draw the planned polyline and (optionally) place a label
            # above the longest horizontal segment.
            path = plan.waypoints
            seg_rects = _rt.render_orthogonal(
                canvas, plan,
                stroke=col, width=sw,
                dasharray=dash,
                marker_end=marker if self.arrow else None,
                src_dot=True,
            )
            if self.label and len(path) >= 2:
                best_seg = None
                best_len = -1.0
                for i in range(len(path) - 1):
                    x1, y1 = path[i]
                    x2, y2 = path[i + 1]
                    if abs(y2 - y1) < 0.5:
                        L = abs(x2 - x1)
                        if L > best_len:
                            best_len = L
                            best_seg = ((x1, y1), (x2, y2))
                if best_seg is None:
                    best_seg = (path[0], path[1])
                from ._labelplacer import place_label
                sz_tok = "small"
                sz = theme.size_px(sz_tok)
                lbl_w = theme.text_width(self.label, sz_tok, bold=False)
                lbl_h = theme.text_height(sz_tok)
                all_anchor_obstacles = [
                    (ox, oy, ox + ow, oy + oh)
                    for ox, oy, ow, oh in anchor_obstacles
                ]
                spine_mid_y = (best_seg[0][1] + best_seg[1][1]) / 2
                seg_obs = [r for r in seg_rects
                           if not (r[1] <= spine_mid_y <= r[3]
                                   and abs(r[3] - r[1]) < 2 * sw + 1)]
                rect, anchor = place_label(
                    segment=best_seg, label_w=lbl_w, label_h=lbl_h,
                    obstacles=all_anchor_obstacles + seg_obs,
                    prefer="above",
                    gap=theme.unit * 0.4,
                )
                x0, y0, x1r, y1r = rect
                mx = (x0 + x1r) / 2
                baseline_y = (y0 + y1r) / 2 + sz * 0.33
                canvas.text(mx, baseline_y, self.label,
                            size=sz, fill=col, italic=True, anchor=anchor)
            return

        # Explicit straight line: render as M/L so the tangent is the line
        # direction (well-defined) and orient="auto" points the arrowhead
        # correctly.  A degenerate Bezier with curvature=0 has zero tangent
        # at endpoints, which makes marker orientation unreliable.
        if self.curvature == 0:
            d = f"M {sx:.2f},{sy:.2f} L {dx:.2f},{dy:.2f}"
            canvas.path(d, stroke=col, fill="none", stroke_width=sw,
                       marker_end=marker, dasharray=dash)
            if self.label:
                mx = (sx + dx) / 2
                my = (sy + dy) / 2
                canvas.text(mx, my - 4, self.label,
                           size=theme.size_px("small"),
                           fill=col, anchor="middle", italic=True)
            return

        dist = ((dx - sx) ** 2 + (dy - sy) ** 2) ** 0.5
        # Control-point distance scales with actual distance.  No minimum
        # floor -- short arrows should be nearly straight, not squiggly.
        c = dist * self.curvature

        # How much to deflect the control point away from the perfectly-
        # perpendicular "out" direction, toward the other endpoint.  A
        # stronger tilt makes the tangent at each endpoint line up with
        # the curve's overall diagonal sweep (not just the side normal),
        # so arrowheads (orient="auto") point along the visual flow.
        # TILT = 0.5 means the control point's off-axis coordinate sits at
        # the midpoint between src and dst on the perpendicular axis,
        # which produces tangents essentially parallel to the line
        # source-to-dest.
        TILT = 0.5

        def out(side, px, py, tx, ty):
            dx_to = tx - px
            dy_to = ty - py
            if side == "right":
                return (px + c,                     py + dy_to * TILT)
            if side == "left":
                return (px - c,                     py + dy_to * TILT)
            if side in ("top", "topleft", "topright"):
                return (px + dx_to * TILT,          py - c)
            if side in ("bottom", "bottomleft", "bottomright"):
                return (px + dx_to * TILT,          py + c)
            return (px, py)

        c1 = out(src_side, sx, sy, dx, dy)
        c2 = out(dst_side, dx, dy, sx, sy)

        # Only override control points for the special "both-below" and
        # "both-above" arcs, which need the curve to bow outward past
        # both endpoints.  For all other cases, the tilt-aware `out()`
        # already produces tangents that follow the overall flow.
        if src_side.startswith("bottom") and dst_side.startswith("bottom"):
            # Both-below arc: bow under the diagram.
            arch_y = max(sy, dy) + self.detour
            sign = 1.0 if dx > sx else -1.0
            pull = abs(dx - sx) * 0.25
            c1 = (sx + sign * pull, arch_y)
            c2 = (dx - sign * pull, arch_y)
        elif src_side.startswith("top") and dst_side.startswith("top"):
            # Both-above arc: bow over the diagram.
            arch_y = min(sy, dy) - self.detour
            sign = 1.0 if dx > sx else -1.0
            pull = abs(dx - sx) * 0.25
            c1 = (sx + sign * pull, arch_y)
            c2 = (dx - sign * pull, arch_y)

        d = (f"M {sx:.2f},{sy:.2f} "
             f"C {c1[0]:.2f},{c1[1]:.2f} {c2[0]:.2f},{c2[1]:.2f} "
             f"{dx:.2f},{dy:.2f}")
        canvas.path(d, stroke=col, fill="none", stroke_width=sw,
                   marker_end=marker, dasharray=dash)

        if self.label:
            mx = (sx + dx) / 2
            my = (sy + dy) / 2
            canvas.text(mx, my - 4, self.label,
                       size=theme.size_px("small"),
                       fill=col, anchor="middle", italic=True)


class Labeled(Element):
    """A ``source`` element followed by a short drawn arrow into a ``label``.

    The clean replacement for the ``Row(Box(...), Text("->"), Math(...))``
    pattern: the author just writes ``Labeled(box, math_label)`` and the
    library draws a proportional horizontal arrow between them, routing
    from the source's right edge to the label's left edge.  Useful for
    the "block -> symbol" annotation pattern (e.g. ``Cross-Entropy Loss``
    flanked by ``L_{MTP}^k``).

    Parameters
    ----------
    source, label : Element
        The block producing the output, and the label explaining it.
    gap : str or float
        Minimum horizontal space between source and label (arrow shaft).
    color : ColorRef or str
        Arrow and (default) label stroke colour.
    align : str
        Cross-axis alignment, passed through to the inner Row.
    """

    def __init__(self, source: Element, label: Element, *,
                 gap: Union[str, float] = "md",
                 color = "text",
                 align: str = "center"):
        self.source = source
        self.label = label
        self.gap = gap
        self.color = color
        self.align = align
        self._compiled: Optional[Element] = None

    def _build(self, theme: Theme) -> Element:
        from .layout import Row
        src_anchor = Anchor("__labeled_src", self.source)
        lbl_anchor = Anchor("__labeled_lbl", self.label)
        inner = Row(src_anchor, lbl_anchor, gap=self.gap, align=self.align)
        return Flowed(inner, flows=[
            Flow("__labeled_src", "__labeled_lbl",
                 src_side="right", dst_side="left",
                 curvature=0.0, color=self.color),
        ])

    def _get(self, theme: Theme) -> Element:
        # Compile fresh every time: Flow carries internal state (like the
        # Flowed._margins_applied flag) that we don't want to leak across
        # measure/render cycles of the same Labeled instance.
        return self._build(theme)

    def measure(self, theme: Theme) -> BBox:
        return self._get(theme).measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._get(theme).render(canvas, x, y, theme)

    def primary_anchor_bbox(self, theme: Theme):
        """Expose the *source* box as the primary anchor so Grid centers
        on the box, not on the whole ``box + arrow + label`` composite.
        """
        src_b = self.source.measure(theme)
        return (0.0, 0.0, src_b.w, src_b.h)

    def content_bbox(self, theme: Theme):
        return self.primary_anchor_bbox(theme)


class Flowed(Element):
    """Render ``child`` and overlay :class:`Flow` arrows between named anchors.

    Use with :class:`Anchor` to tag the elements you want to connect::

        diagram = Flowed(
            child=Row(
                Anchor("ae", action_encoder),
                Anchor("dt", diffusion_transformer),
            ),
            flows=[Flow("ae", "dt", src_side="bottom", dst_side="bottomright")],
        )

    Before rendering, Flowed runs a *pre-pass* that walks the child tree,
    finds all named anchors, and inflates their margins according to the
    flows that reference them.  This ensures every flow has visible space
    for its arrow shaft without the author having to tune Row/Column gaps
    by hand.  The ``min_flow_space`` parameter controls how much margin
    is added on the flow-connecting side (default 10 px per side -- i.e.
    ~20 extra px between two horizontally-connected siblings).
    """

    def __init__(self, child: Element, flows: Sequence = (),
                 min_flow_space: float = 10.0):
        self.child = child
        self.flows = list(flows)
        self.min_flow_space = min_flow_space
        self._margins_applied = False

    def _collect_anchors(self, elem, out):
        if isinstance(elem, Anchor):
            out.setdefault(elem.name, elem)
        # Recurse into common container attributes.  This covers Row, Column,
        # Stack, BlockGroup, Region, Padded, Framed, FixedSize, etc.
        for attr in ("children",):
            children = getattr(elem, attr, None)
            if children is not None:
                for c in children:
                    if c is not None:
                        self._collect_anchors(c, out)
        for attr in ("child",):
            child = getattr(elem, attr, None)
            if child is not None:
                self._collect_anchors(child, out)
        # Grid stores cells in a list of dicts keyed by row name -- recurse
        # into every value (including tuple-keyed spanning cells).
        cols = getattr(elem, "columns", None)
        if isinstance(cols, list):
            for col in cols:
                if isinstance(col, dict):
                    for key, val in col.items():
                        if isinstance(key, str) and key.startswith("_"):
                            continue
                        if isinstance(val, Element):
                            self._collect_anchors(val, out)

    def _apply_flow_margins(self):
        if self._margins_applied:
            return
        self._margins_applied = True
        anchors: dict = {}
        self._collect_anchors(self.child, anchors)
        m = self.min_flow_space
        for flow in self.flows:
            if isinstance(flow, Flow):
                src = anchors.get(flow.src)
                dst = anchors.get(flow.dst)
                # If the flow's side is "auto", skip margin inflation --
                # we don't know which boundary the flow will attach to.
                if src is not None and flow.src_side != "auto":
                    src._bump_margin(flow.src_side, m)
                if dst is not None and flow.dst_side != "auto":
                    dst._bump_margin(flow.dst_side, m)
            elif isinstance(flow, Bus) and flow.label:
                # Labelled Bus (e.g. a fan-in ``concatenation`` junction)
                # needs vertical breathing room for its side label inside
                # the gap between source and sink rows.  Bump the sink's
                # margin on the face closest to the sources, so the label
                # sits cleanly in that inflated gap.
                for name in flow.sources:
                    a = anchors.get(name)
                    if a is not None:
                        a._bump_margin("top", m * 0.6)
                for name in flow.sinks:
                    a = anchors.get(name)
                    if a is not None:
                        a._bump_margin("bottom", m * 0.6)

    def measure(self, theme: Theme) -> BBox:
        self._apply_flow_margins()
        return self.child.measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._apply_flow_margins()
        my_registry: dict = {}
        existing = _anchor_stack.get()
        new_stack = (list(existing) if existing else []) + [my_registry]
        token = _anchor_stack.set(new_stack)
        try:
            self.child.render(canvas, x, y, theme)
        finally:
            _anchor_stack.reset(token)
        self._assign_edge_shares(my_registry)
        for flow in self.flows:
            flow._render(canvas, theme, my_registry)

    def _assign_edge_shares(self, registry: dict) -> None:
        """Distribute multiple flows that attach to the same anchor edge
        along that edge, instead of piling them onto the midpoint.

        Groups flows by ``(anchor_name, resolved_side)`` and assigns
        fractional taps evenly: ``(i+1)/(n+1)`` for a group of ``n``.
        Within a group, flows are ordered by the *other* endpoint's
        perpendicular coordinate so neighbouring attachments correspond
        to neighbouring counterparts -- e.g. two flows entering a box's
        top from the left and right get their taps on the left and
        right of that top edge respectively.
        """
        flow_endpoints = []
        for flow in self.flows:
            if not isinstance(flow, Flow):
                continue
            sb = registry.get(flow.src)
            db = registry.get(flow.dst)
            if sb is None or db is None:
                continue
            src_side = (flow._auto_side(sb, db)
                        if flow.src_side == "auto" else flow.src_side)
            dst_side = (flow._auto_side(db, sb)
                        if flow.dst_side == "auto" else flow.dst_side)
            flow_endpoints.append((flow, sb, db, src_side, dst_side))

        buckets: dict = {}
        for entry in flow_endpoints:
            flow, sb, db, src_side, dst_side = entry
            buckets.setdefault((flow.src, src_side), []).append(
                ("src", entry))
            buckets.setdefault((flow.dst, dst_side), []).append(
                ("dst", entry))

        for (anchor_name, side), members in buckets.items():
            if len(members) <= 1:
                # Single flow on this edge -- keep the midpoint default.
                for role, entry in members:
                    flow, sb, db, ssd, dsd = entry
                    if role == "src":
                        flow._share_src_frac = 0.5
                    else:
                        flow._share_dst_frac = 0.5
                continue

            def sort_key(m):
                role, entry = m
                flow, sb, db, ssd, dsd = entry
                other = db if role == "src" else sb
                ox, oy, ow, oh = other
                return (ox + ow / 2) if side in ("top", "bottom") else (oy + oh / 2)

            members.sort(key=sort_key)
            n = len(members)
            for i, (role, entry) in enumerate(members):
                flow, sb, db, ssd, dsd = entry
                frac = (i + 1) / (n + 1)
                if role == "src":
                    flow._share_src_frac = frac
                else:
                    flow._share_dst_frac = frac


# ---------------------------------------------------------------------------
# MatchSize -- container that equalises children along an axis
# ---------------------------------------------------------------------------

class MatchSize(Element):
    """Wrap a list of children, stretching them to a common dimension.

    Eliminates the manual ``height=132`` repetition that authors otherwise
    do to make sibling boxes line up.  Wrap them in MatchSize and the
    container computes the max intrinsic dimension and forces every child
    to it via :class:`FixedSize`.

    Parameters
    ----------
    *children : Element
        The siblings to equalise.
    axis : str
        ``"height"`` (default) -- equalise heights.  Useful when laying out
        in a Row.
        ``"width"``  -- equalise widths.  Useful when laying out in a Column.
    arrange : str or None
        If ``"row"`` or ``"column"``, the equalised children are also wrapped
        in the corresponding container so the user doesn't write the
        ``Row(...)`` themselves.  Default ``None`` returns just the
        equalised children laid out by the surrounding parent.
    gap : str or float
        Used only when ``arrange`` is set.
    align : str
        Cross-axis alignment when ``arrange`` is set.
    """

    def __init__(self, *children: Element,
                 axis: str = "height",
                 arrange: Optional[str] = None,
                 gap: Union[str, float] = "md",
                 align: str = "center"):
        self.children = list(children)
        self.axis = axis
        self.arrange = arrange
        self.gap = gap
        self.align = align

    def _equalised(self, theme: Theme):
        from .layout import FixedSize, Row, Column
        sizes = [c.measure(theme) for c in self.children]
        if self.axis == "height":
            target = max(s.h for s in sizes) if sizes else 0
            return [FixedSize(c, height=target) for c in self.children]
        else:
            target = max(s.w for s in sizes) if sizes else 0
            return [FixedSize(c, width=target) for c in self.children]

    def _arranged(self, theme: Theme):
        from .layout import Row, Column
        children = self._equalised(theme)
        if self.arrange == "row":
            return Row(*children, gap=self.gap, align=self.align)
        if self.arrange == "column":
            return Column(*children, gap=self.gap, align=self.align)
        # No explicit arrangement: pack into a Row by default for height,
        # Column for width.
        if self.axis == "height":
            return Row(*children, gap=self.gap, align=self.align)
        return Column(*children, gap=self.gap, align=self.align)

    def measure(self, theme: Theme) -> BBox:
        return self._arranged(theme).measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._arranged(theme).render(canvas, x, y, theme)


# ---------------------------------------------------------------------------
# Group -- children + automatic underbrace label
# ---------------------------------------------------------------------------

class Group(Element):
    """A row of children with an automatic brace + label beneath.

    Replaces the manual three-step pattern::

        chips = Row(*chip_elements)
        brace = Brace(span=measure(chips).w, label=...)
        column = Column(chips, brace)

    Now: ``Group("Visual Tokens", *chips)``.

    The brace span auto-fits the children's combined width.
    """

    def __init__(self, label: str, *children: Element,
                 gap: Union[str, float] = "xs",
                 brace_color = "muted",
                 brace_height: float = 6.0,
                 spacing: float = 4.0):
        self.label = label
        self.children = list(children)
        self.gap = gap
        self.brace_color = brace_color
        self.brace_height = brace_height
        self.spacing = spacing

    def _row(self):
        from .layout import Row
        return Row(*self.children, gap=self.gap, align="center")

    def measure(self, theme: Theme) -> BBox:
        from .layout import Column, Spacer
        row = self._row()
        rb = row.measure(theme)
        brace = Brace(rb.w, self.label, direction="down",
                      color=self.brace_color, height=self.brace_height)
        bb = brace.measure(theme)
        return BBox(max(rb.w, bb.w), rb.h + self.spacing + bb.h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        from .layout import Column, Spacer
        row = self._row()
        rb = row.measure(theme)
        size = self.measure(theme)
        # center the row within the outer width
        rx = x + (size.w - rb.w) / 2
        row.render(canvas, rx, y, theme)
        brace = Brace(rb.w, self.label, direction="down",
                      color=self.brace_color, height=self.brace_height)
        brace.render(canvas, rx, y + rb.h + self.spacing, theme)


# ---------------------------------------------------------------------------
# Region -- a labeled bordered *container* with asymmetric padding.
#
# Unlike BlockGroup (symmetric padding around a centered child), Region is
# designed for annotation groupings that should preserve sibling alignment:
#   * no left padding -- child's left edge is flush with Region's left edge
#     so siblings using align="start" stay aligned
#   * symmetric top/bottom padding -- child's vertical center coincides
#     with Region's bbox center, so a sibling Row using align="center"
#     centers with the child content (not the label area)
#   * right padding for visual breathing room for the border
#   * top padding equal to label height so the label sits on the top border
#     without crowding the child
#
# This is the right shape for "Apply" / "Update" / "Frozen" / "Trainable"
# style annotation groupings that sit inline in an existing layout.
# ---------------------------------------------------------------------------

class Region(Element):
    """A labeled bordered container with proper inside padding and outside label.

    Resolves three competing needs simultaneously:

    1. **Label sits above the border** (outside), like the original overlay --
       authors don't want the label visually inside the bordered box.

    2. **Inner padding on every side** -- children have visible breathing
       room from the border line.

    3. **Horizontal alignment with non-Region siblings is preserved.**
       The child inside Region stays flush with Region's bbox left edge;
       the border extends *leftward into the parent's gap* between Region
       and its preceding sibling.  This works because containers always
       reserve gap space between children anyway.  No other layout tricks
       required.

    The bbox is ``(child_w + pad_x, child_h + label_h + 2*pad_y)``.
    The *rendered* border spans ``(x - pad_x, y + label_h)`` to
    ``(x + child_w + pad_x, y + bbox_h)`` -- wider than the bbox by
    ``pad_x`` on the left, encroaching into the parent gap.

    Parameters
    ----------
    child : Element
        Content inside the region.
    label : str, optional
        Header text drawn above the top border.
    color : ColorRef or str
        Border and label colour.
    fill : ColorRef or str, optional
        Background tint behind the child.
    dashed : bool
        Border style.
    pad_x : float
        Horizontal padding (both sides; left side extends into parent gap).
    pad_y : float
        Vertical padding inside the border (top and bottom).
    label_align : str
        ``"start"`` (default), ``"center"``, or ``"end"``.
    label_size : str
        Theme size token for the label.
    """

    def __init__(self, child: Element, *,
                 label: Optional[str] = None,
                 color = "muted",
                 fill = None,
                 dashed: bool = True,
                 pad_x: float = 8.0,
                 pad_y: float = 5.0,
                 margin_x: float = 6.0,
                 margin_y: float = 6.0,
                 label_align: str = "start",
                 label_size: str = "label"):
        self.child = child
        self.label = label
        self.color = color
        self.fill = fill
        self.dashed = dashed
        self.pad_x = pad_x
        self.pad_y = pad_y
        # Outer margins: reserved space between Region's border and
        # neighbouring content.  margin_x adds to the bbox on the right only
        # (so the child stays flush-left for sibling alignment).  margin_y
        # is symmetric top/bottom.
        self.margin_x = margin_x
        self.margin_y = margin_y
        self.label_align = label_align
        self.label_size = label_size

    def _label_h(self, theme: Theme) -> float:
        if not self.label:
            return 0.0
        return theme.text_height(self.label_size) + theme.unit * 0.4

    def measure(self, theme: Theme) -> BBox:
        b = self.child.measure(theme)
        lh = self._label_h(theme)
        # Horizontal: child + right-inner-pad + right-outer-margin
        # (left inner pad extends into parent gap; no left outer margin
        # so sibling alignment is preserved)
        w = b.w + self.pad_x + self.margin_x
        # Vertical: lh (label above border) + top_pad + child + bot_pad
        # where bot_pad = lh + pad_y to keep child at bbox vertical centre
        # (balances the label above the border).  Plus margin on each side.
        h = b.h + 2 * lh + 2 * self.pad_y + 2 * self.margin_y
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        b = self.child.measure(theme)
        lh = self._label_h(theme)
        size = self.measure(theme)
        col = theme.color_of(self.color)
        fill_col = theme.color_of(self.fill) if self.fill is not None else "none"

        # Border top: below the label-h area and below the top margin_y
        border_x = x - self.pad_x
        border_w = b.w + 2 * self.pad_x
        border_top = y + self.margin_y + lh
        # Border height: pad_y + child + pad_y + lh  (lh extra at bottom
        # balances the label space above).
        border_h = b.h + 2 * self.pad_y + lh
        canvas.rect(
            border_x, border_top, border_w, border_h,
            fill=fill_col, stroke=col,
            stroke_width=theme.hairline,
            rx=theme.panel_radius * 1.5,
            dasharray="4,3" if self.dashed else None,
        )

        # Publish the border rectangle to every active anchor registry
        # under a `__region_<id>` key.  Connector routers consult these
        # keys to compute required / forbidden boundary crossings.
        stack = _anchor_stack.get()
        if stack is not None:
            key = f"__region_{id(self):x}"
            for reg in stack:
                reg[key] = (border_x, border_top, border_w, border_h)

        # Label in the lh space above the border (and below top margin_y).
        if self.label:
            lbl_w = theme.text_width(self.label, self.label_size, bold=True)
            if self.label_align == "center":
                lx = border_x + (border_w - lbl_w) / 2
            elif self.label_align == "end":
                lx = border_x + border_w - theme.unit - lbl_w
            else:
                lx = border_x + theme.unit
            canvas.text(lx,
                       y + self.margin_y + theme.size_px(self.label_size) * 0.85,
                       self.label, size=theme.size_px(self.label_size),
                       fill=col, weight="700", anchor="start")

        # Child: flush at bbox left (x), inside border with pad_y above it.
        self.child.render(canvas, x, border_top + self.pad_y, theme)


# ---------------------------------------------------------------------------
# Bus -- multi-source / multi-sink connector.
#
# Covers the "one-to-many" and "shared-by-all" cases that a pairwise Flow
# can only approximate.  Three common shapes:
#
#   1. Shared horizontal bus: all endpoints are roughly co-linear at
#      similar y -- draw a single horizontal line connecting them at
#      that y, with short taps down into each.
#
#   2. Fan-out tree: one source, many sinks -- a stem from the source
#      meets a horizontal spine; each sink is tapped off the spine.
#
#   3. Fan-in tree: many sources, one sink -- mirror of fan-out.
#
# The author writes only endpoint names; the library picks the shape.
# ---------------------------------------------------------------------------

class Bus:
    """Multi-endpoint connector routed through a single spine.

    Use when the same signal is shared by several sinks (e.g. a "Shared"
    weight layer) or many sources converge into one sink (e.g. expert
    outputs combining at an ``+``).  Authoring is endpoint-only::

        Bus(sources="main_out",
            sinks=["mtp1_out", "mtp2_out", "mtp3_out"],
            label="Shared",
            dashed=True)

    Parameters
    ----------
    sources, sinks : str or list of str
        Anchor names.
    label : str, optional
        Rendered once along the bus spine.
    dashed : bool
        Bus style.
    color : ColorRef or str
    arrow : bool
        Draw arrowheads at sink ends (default True).
    """

    def __init__(self, sources, sinks, *,
                 label: Optional[str] = None,
                 dashed: bool = False,
                 color = "muted_label",
                 arrow: bool = True):
        self.sources = [sources] if isinstance(sources, str) else list(sources)
        self.sinks   = [sinks]   if isinstance(sinks,   str) else list(sinks)
        self.label = label
        self.dashed = dashed
        self.color = color
        self.arrow = arrow

    def _draw_placed_label(self, canvas: Canvas, theme: Theme,
                           segment, obstacles, *, color: str,
                           size_token: str = "tiny",
                           prefer: str = "above",
                           mask_bg: bool = False) -> None:
        """Place ``self.label`` on ``segment`` avoiding ``obstacles``.

        Uses the geometric label placer so the label dodges structural
        lines (T-bars, taps, other boxes).  When ``mask_bg`` is True, a
        white rectangle is drawn behind the label so a dashed line
        reads as passing cleanly behind the text.
        """
        if not self.label:
            return
        from ._labelplacer import place_label
        sz = theme.size_px(size_token)
        lbl_w = theme.text_width(self.label, size_token, bold=False)
        lbl_h = theme.text_height(size_token)
        rect, anchor = place_label(
            segment=segment, label_w=lbl_w, label_h=lbl_h,
            obstacles=list(obstacles), prefer=prefer,
            gap=theme.unit * 0.35,
        )
        x0, y0, x1, y1 = rect
        if mask_bg:
            bg_pad = theme.unit * 0.25
            canvas.rect(x0 - bg_pad, y0 - bg_pad,
                        (x1 - x0) + 2 * bg_pad,
                        (y1 - y0) + 2 * bg_pad,
                        fill=theme.color_of("bg"), stroke="none")
        mx = (x0 + x1) / 2
        baseline_y = (y0 + y1) / 2 + sz * 0.33
        canvas.text(mx, baseline_y, self.label, size=sz, fill=color,
                    italic=True, anchor=anchor)

    def _render(self, canvas: Canvas, theme: Theme, registry: dict) -> None:
        src_boxes = [registry[n] for n in self.sources if n in registry]
        dst_boxes = [registry[n] for n in self.sinks   if n in registry]
        if not src_boxes or not dst_boxes:
            return

        col = theme.color_of(self.color)
        dasharray = "4,3" if self.dashed else None
        sw = theme.connector
        marker = (canvas.define_arrow_marker(
                      color=col, stroke_width=sw,
                      arrow_size=getattr(theme, "arrow_size", None),
                      name_hint="bus")
                  if self.arrow else None)

        # Filter out routing-region pseudo-entries from the obstacle
        # list: those are bbox regions registered by Grid panels, not
        # real drawn boxes, and must not block label placement.
        box_obstacles = [(b[0], b[1], b[0] + b[2], b[1] + b[3])
                         for b in (src_boxes + dst_boxes)]

        all_boxes = src_boxes + dst_boxes
        centres_y = [b[1] + b[3] / 2 for b in all_boxes]
        avg_h = sum(b[3] for b in all_boxes) / len(all_boxes)
        y_spread = max(centres_y) - min(centres_y)
        if y_spread < avg_h * 0.5:
            # Shared-row: line lives in the gaps between consecutive boxes
            # (the boxes themselves "mask" the middle by being rendered on top).
            sorted_boxes = sorted(all_boxes, key=lambda b: b[0])
            mid_y = sum(centres_y) / len(centres_y)
            for b_left, b_right in zip(sorted_boxes, sorted_boxes[1:]):
                x_from = b_left[0] + b_left[2]
                x_to   = b_right[0]
                canvas.line(x_from, mid_y, x_to, mid_y,
                            stroke=col, stroke_width=sw,
                            dasharray=dasharray)
            if self.label:
                for b_left, b_right in zip(sorted_boxes, sorted_boxes[1:]):
                    x_from = b_left[0] + b_left[2]
                    x_to   = b_right[0]
                    # Place on the centred line gap; mask the dashed line
                    # behind the label.  The placer chooses above/below
                    # automatically based on which side has more room.
                    self._draw_placed_label(
                        canvas, theme,
                        segment=((x_from, mid_y), (x_to, mid_y)),
                        obstacles=box_obstacles,
                        color=col,
                        size_token="tiny",
                        prefer="above",
                        mask_bg=True,
                    )
            return

        # Otherwise fan-out/fan-in: one-side (sources or sinks) is clustered,
        # other side is spread out.  Build a spine OFFSET from the clustered
        # side toward the spread side, and route taps to each endpoint.
        # Pick orientation by the dominant geometry.
        all_x = [b[0] + b[2] / 2 for b in all_boxes]
        x_spread = max(all_x) - min(all_x)
        horizontal = x_spread >= y_spread

        if horizontal:
            # Spine is horizontal, spread is along x.  Decide which cluster
            # is "below" (source) vs "above" (sink) by mean y.
            src_mean_y = sum(b[1] + b[3] / 2 for b in src_boxes) / len(src_boxes)
            dst_mean_y = sum(b[1] + b[3] / 2 for b in dst_boxes) / len(dst_boxes)
            source_below = src_mean_y > dst_mean_y
            if source_below:
                src_edge = lambda b: (b[0] + b[2] / 2, b[1])              # top
                dst_edge = lambda b: (b[0] + b[2] / 2, b[1] + b[3])       # bottom
                # Spine sits in the middle of the gap between the source
                # tops and the sink bottom, so the side label has clear
                # room above it without touching the sink.
                src_top = max(b[1] for b in src_boxes)
                dst_bot = min(b[1] + b[3] for b in dst_boxes)
                spine_y = (src_top + dst_bot) / 2
            else:
                src_edge = lambda b: (b[0] + b[2] / 2, b[1] + b[3])
                dst_edge = lambda b: (b[0] + b[2] / 2, b[1])
                src_bot = min(b[1] + b[3] for b in src_boxes)
                dst_top = max(b[1] for b in dst_boxes)
                spine_y = (src_bot + dst_top) / 2

            # Single-sink fan-in (``concatenation`` junction): taps from
            # each source rise to a short horizontal bar, then ONE arrow
            # from the centre of that bar goes all the way to the sink.
            is_fan_in = len(dst_boxes) == 1 and len(src_boxes) > 1
            src_taps_x = [src_edge(b)[0] for b in src_boxes]

            line_obstacles = []  # drawn line rects we'll want to avoid
            for b in src_boxes:
                px, py = src_edge(b)
                canvas.line(px, py, px, spine_y,
                            stroke=col, stroke_width=sw, dasharray=dasharray)
                # tap obstacle: thin vertical stripe, sw wide
                y_lo, y_hi = min(py, spine_y), max(py, spine_y)
                line_obstacles.append((px - sw, y_lo, px + sw, y_hi))
            if is_fan_in:
                x0 = min(src_taps_x); x1 = max(src_taps_x)
                canvas.line(x0, spine_y, x1, spine_y,
                            stroke=col, stroke_width=sw, dasharray=dasharray)
                # T-bar obstacle -- pad it by half a text-line's height so
                # the placer never places a label flush against it.
                bar_pad = theme.unit * 0.5
                line_obstacles.append((x0, spine_y - bar_pad,
                                       x1, spine_y + bar_pad))
                bar_mid_x = (x0 + x1) / 2
                dpx, dpy = dst_edge(dst_boxes[0])
                attrs = {"stroke": col, "stroke_width": sw}
                if dasharray:
                    attrs["dasharray"] = dasharray
                if self.arrow:
                    attrs["marker_end"] = marker
                canvas.line(bar_mid_x, spine_y, dpx, dpy, **attrs)
                # sink arrow obstacle
                y_lo, y_hi = min(spine_y, dpy), max(spine_y, dpy)
                line_obstacles.append((bar_mid_x - sw, y_lo,
                                       bar_mid_x + sw, y_hi))
                if self.label:
                    # For a fan-in, prefer the empty space BETWEEN the
                    # source boxes and the T-bar (i.e. on the source side
                    # of the bar).  That's "below" the bar when sources
                    # are below, or "above" when sources are above.
                    prefer = "below" if source_below else "above"
                    self._draw_placed_label(
                        canvas, theme,
                        segment=((x0, spine_y), (x1, spine_y)),
                        obstacles=box_obstacles + line_obstacles,
                        color=col,
                        size_token="micro",
                        prefer=prefer,
                        mask_bg=False,
                    )
            else:
                # Fan-out (or symmetric): taps from spine to each sink,
                # with an arrowhead on each.  Spine spans all tap xs.
                taps_x = list(src_taps_x)
                for b in dst_boxes:
                    px, py = dst_edge(b)
                    attrs = {"stroke": col, "stroke_width": sw}
                    if dasharray:
                        attrs["dasharray"] = dasharray
                    if self.arrow:
                        attrs["marker_end"] = marker
                    canvas.line(px, spine_y, px, py, **attrs)
                    taps_x.append(px)
                    y_lo, y_hi = min(spine_y, py), max(spine_y, py)
                    line_obstacles.append((px - sw, y_lo, px + sw, y_hi))
                x0 = min(taps_x); x1 = max(taps_x)
                canvas.line(x0, spine_y, x1, spine_y,
                            stroke=col, stroke_width=sw, dasharray=dasharray)
                if self.label:
                    prefer = "above" if source_below else "below"
                    self._draw_placed_label(
                        canvas, theme,
                        segment=((x0, spine_y), (x1, spine_y)),
                        obstacles=box_obstacles + line_obstacles,
                        color=col,
                        size_token="tiny",
                        prefer=prefer,
                        mask_bg=False,
                    )
        else:
            # Vertical spine (left-right cluster spread vertically).
            src_mean_x = sum(b[0] + b[2] / 2 for b in src_boxes) / len(src_boxes)
            dst_mean_x = sum(b[0] + b[2] / 2 for b in dst_boxes) / len(dst_boxes)
            source_left = src_mean_x < dst_mean_x
            if source_left:
                spine_x = (max(b[0] + b[2] for b in src_boxes)
                           + min(b[0] for b in dst_boxes)) / 2
                src_edge = lambda b: (b[0] + b[2], b[1] + b[3] / 2)
                dst_edge = lambda b: (b[0], b[1] + b[3] / 2)
            else:
                spine_x = (min(b[0] for b in src_boxes)
                           + max(b[0] + b[2] for b in dst_boxes)) / 2
                src_edge = lambda b: (b[0], b[1] + b[3] / 2)
                dst_edge = lambda b: (b[0] + b[2], b[1] + b[3] / 2)
            taps_y = []
            line_obstacles = []
            for b in src_boxes:
                px, py = src_edge(b)
                canvas.line(px, py, spine_x, py,
                            stroke=col, stroke_width=sw, dasharray=dasharray)
                taps_y.append(py)
                x_lo, x_hi = min(px, spine_x), max(px, spine_x)
                line_obstacles.append((x_lo, py - sw, x_hi, py + sw))
            for b in dst_boxes:
                px, py = dst_edge(b)
                attrs = {"stroke": col, "stroke_width": sw}
                if dasharray:
                    attrs["dasharray"] = dasharray
                if self.arrow:
                    attrs["marker_end"] = marker
                canvas.line(spine_x, py, px, py, **attrs)
                taps_y.append(py)
                x_lo, x_hi = min(spine_x, px), max(spine_x, px)
                line_obstacles.append((x_lo, py - sw, x_hi, py + sw))
            y0 = min(taps_y); y1 = max(taps_y)
            canvas.line(spine_x, y0, spine_x, y1,
                        stroke=col, stroke_width=sw, dasharray=dasharray)
            if self.label:
                prefer = "right" if source_left else "left"
                self._draw_placed_label(
                    canvas, theme,
                    segment=((spine_x, y0), (spine_x, y1)),
                    obstacles=box_obstacles + line_obstacles,
                    color=col,
                    size_token="tiny",
                    prefer=prefer,
                    mask_bg=False,
                )
