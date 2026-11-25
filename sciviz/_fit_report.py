"""Target-width fit report (:meth:`Diagram.fit_report`).

A fitted figure either lands on ``target_width_pt`` or it does not; when
it does not, compressing spacing further is not the answer (spacing has
print floors, fonts never shrink). The report says what the fit chose
and what holds the width up: the width-critical path through the layout
tree, the authored numeric gaps on it, and any ink painted outside the
laid-out box.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .core import Canvas, Element, Theme


@dataclass(frozen=True)
class FitReport:
    """What a :class:`~sciviz.Diagram` width fit chose and why.

    Attributes
    ----------
    target : float or None
        ``target_width_pt`` (``None`` for an unfitted diagram).
    width, height : float
        The exported page (:meth:`Diagram.page_size`).
    layout_width, layout_height : float
        The laid-out box (:meth:`Diagram.measure`).
    density : float
        Spacing density the fit chose (1.0 = authored spacing).
    wrap_scale : float
        Wrap-budget scale the fit chose (1.0 = authored budget).
    trials : int
        Candidate layouts the fit measured.
    seconds : float
        Wall time the fit took.
    overflow : tuple of (kind, side, extent)
        Ink outside the laid-out body box, deepest first
        (see :func:`sciviz.auto.ink.overflow_items`).
    drivers : tuple of (depth, what, width)
        The width-critical path, breadth first: at each depth, the
        parts that set their container's width (every part of a row,
        the widest part of anything else) and the authored numeric gaps
        between them, with natural widths in points.
    """

    target: Optional[float]
    width: float
    height: float
    layout_width: float
    layout_height: float
    density: float
    wrap_scale: float
    trials: int
    seconds: float
    overflow: Tuple[Tuple[str, str, float], ...]
    drivers: Tuple[Tuple[int, str, float], ...]

    @property
    def landed(self) -> bool:
        """Whether the page is within the half-point snap of the target."""
        return self.target is None or self.width <= self.target + 0.5

    def __str__(self) -> str:
        head = (f"page {self.width:.1f} x {self.height:.1f} pt "
                f"(layout {self.layout_width:.1f} x "
                f"{self.layout_height:.1f})")
        if self.target is not None:
            state = "landed" if self.landed else (
                f"OVER by {self.width - self.target:.1f} pt")
            head += f"; target {self.target:g} pt {state}"
        lines = [head,
                 f"density {self.density:.3f}, wrap scale "
                 f"{self.wrap_scale:.3f}, {self.trials} trials in "
                 f"{self.seconds:.1f} s"]
        if self.overflow:
            lines.append("ink outside the layout: " + ", ".join(
                f"{k} {s} {e:.1f} pt" for k, s, e in self.overflow))
        if self.drivers:
            lines.append("width drivers:")
            lines.extend(f"  {w:7.1f} pt  {'  ' * depth}{what}"
                         for depth, what, w in self.drivers)
        return "\n".join(lines)


_WRAPPER_ATTRS = ("child", "body", "header", "footer", "above", "below")


def _describe(elem) -> str:
    name = type(elem).__name__
    for attr in ("content", "label", "title", "text", "name"):
        val = getattr(elem, attr, None)
        if isinstance(val, str) and val.strip():
            text = " ".join(val.split())
            if len(text) > 40:
                text = text[:39] + "..."
            return f'{name} "{text}"'
    return name


def _parts(elem) -> List[Element]:
    kids = getattr(elem, "children", None)
    parts = [c for c in kids if isinstance(c, Element)] if kids else []
    for attr in _WRAPPER_ATTRS:
        c = getattr(elem, attr, None)
        if isinstance(c, Element) and c not in parts:
            parts.append(c)
    return parts


def width_drivers(body: Element, theme: Theme, *, limit: int = 12
                  ) -> Tuple[Tuple[int, str, float], ...]:
    """The width-critical path of ``body`` under ``theme``.

    A horizontal container (:class:`~sciviz.Row` and subclasses) spends
    its width on every part plus its gaps, so every part is on the path
    and an authored numeric ``gap`` (which never compresses) is listed
    beside them; any other container is as wide as its widest part, so
    the path follows that part alone. Entries are ``(depth, what,
    width)`` in breadth-first order -- the top-level split of the width
    first -- at most ``limit`` of them.

    ``body`` should be unmeasured: layout stretches siblings to a shared
    width, so natural widths are taken from a throwaway copy of each
    part (``body`` itself is never measured).
    """
    from .layout import Row

    def natural(elem: Element) -> float:
        try:
            return copy.deepcopy(elem).measure(theme).w
        except Exception:  # pragma: no cover -- uncopyable element
            return elem.measure(theme).w

    def on_path(elem: Element) -> List[Element]:
        parts = _parts(elem)
        if len(parts) <= 1 or isinstance(elem, Row):
            return parts
        widths = [natural(p) for p in parts]
        return [parts[widths.index(max(widths))]]

    out: List[Tuple[int, str, float]] = []
    level, depth = [body], 0
    while level and len(out) < limit and depth < 40:
        nxt: List[Element] = []
        for elem in level:
            parts = on_path(elem)
            gap = getattr(elem, "gap", None)
            if (isinstance(elem, Row) and isinstance(gap, (int, float))
                    and not isinstance(gap, bool) and gap > 0
                    and len(parts) > 1):
                out.append((depth, f"numeric gap={gap:g} x "
                            f"{len(parts) - 1} in {_describe(elem)}",
                            gap * (len(parts) - 1)))
            for p in parts:
                if len(parts) > 1 or not _parts(p):
                    out.append((depth, _describe(p), natural(p)))
                nxt.append(p)
        level, depth = nxt, depth + 1
    return tuple(out[:limit])


def build_fit_report(diagram) -> FitReport:
    """Assemble the :class:`FitReport` for ``diagram`` (fits if needed)."""
    from .auto.ink import overflow_items
    from .composition import Flowed
    from .connect._resolver import _FlowResolver

    page = diagram.page_size()
    layout = diagram.measure()
    theme = diagram._layout_theme()
    base = diagram.theme
    density = theme.unit / base.unit if base.unit else 1.0
    wrap = (theme.wrap_budget / base.wrap_budget
            if base.wrap_budget else 1.0)
    stats = diagram._fit_stats or {}

    try:
        body = copy.deepcopy(diagram.body)
    except Exception:  # pragma: no cover -- uncopyable author tree
        body = diagram.body
    resolved = (body if isinstance(body, (Flowed, _FlowResolver))
                else _FlowResolver(body))
    size = resolved.measure(theme)
    canvas = Canvas(default_font_family=theme.font_family,
                    text_stroke_ratio=theme.text_stroke_ratio)
    resolved.render(canvas, 0.0, 0.0, theme)
    overflow = tuple(overflow_items(canvas, (0.0, 0.0, size.w, size.h)))
    pristine = getattr(diagram, "_pristine_body", None)
    drivers = width_drivers(copy.deepcopy(pristine if pristine is not None
                                          else diagram.body), theme)
    return FitReport(
        target=diagram.target_width_pt,
        width=page.w, height=page.h,
        layout_width=layout.w, layout_height=layout.h,
        density=density, wrap_scale=wrap,
        trials=int(stats.get("trials", 0)),
        seconds=float(stats.get("seconds", 0.0)),
        overflow=overflow, drivers=drivers)
