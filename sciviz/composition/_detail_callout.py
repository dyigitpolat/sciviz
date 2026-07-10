"""Semantic overview-to-detail callouts.

``DetailCallout`` binds an anchor nested anywhere in an overview element to a
detail element.  It deliberately owns only the generic presentation policy:
whether the detail sits beside or below the overview and how the leader is
routed.  The selected component and the contents of its detail remain author
data.

The implementation lowers to the existing layout and connector vocabulary so
it inherits normal measurement, obstacle avoidance, and theme behaviour.
"""

from __future__ import annotations

from math import log
from typing import Literal

from ..core import BBox, Canvas, Element, Theme
from ..layout import Column, Row
from ._anchor import Anchor, _anchor_stack


Placement = Literal["auto", "right", "below"]


class _LeaderPadding(Element):
    """Theme-derived breathing room for router detours and their label."""

    def __init__(self, child: Element, *, label: str | None) -> None:
        self.child = child
        self.label = label

    def _pad(self, theme: Theme) -> float:
        if self.label is None:
            # Unlabelled zoom rails are straight and remain inside the
            # overview/detail corridor.  They need only a rasterisation
            # cushion; the historical full ``lg`` moat accumulated at every
            # nested detail level and made architecture figures sprawl.
            return theme.unit * 0.75
        pad = theme.gap_px("lg")
        if self.label is not None:
            # Orthogonal leaders may use the outer corridor; reserve one
            # additional routing unit beyond the text box and label gap.
            pad = max(
                pad,
                theme.text_height("small") + theme.unit * 3.0,
                theme.text_width(self.label, "small") / 2.0 + theme.unit,
            )
        return pad

    def measure(self, theme: Theme) -> BBox:
        child = self.child.measure(theme)
        pad = self._pad(theme)
        return BBox(child.w + 2.0 * pad, child.h + 2.0 * pad)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        pad = self._pad(theme)
        self.child.render(canvas, x + pad, y + pad, theme)


class _SourceOutline(Element):
    """Paint the selected source extent after its anchor is registered."""

    is_layout_invisible = True

    def __init__(self, source: str) -> None:
        self.source = source

    def measure(self, theme: Theme) -> BBox:
        return BBox(0.0, 0.0)

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:
        stack = _anchor_stack.get()
        if not stack:
            return
        bbox = stack[-1].get(self.source)
        if bbox is None:
            return
        bx, by, bw, bh = bbox
        outset = theme.unit * 0.45
        canvas.rect(
            bx - outset,
            by - outset,
            bw + 2 * outset,
            bh + 2 * outset,
            fill="none",
            stroke=theme.paint_of("border_strong"),
            stroke_width=theme.hairline,
            rx=max(theme.panel_radius, theme.unit * 0.55),
            dasharray="4,3",
        )


def _anchor_names(root: Element) -> tuple[str, ...]:
    """Return anchor names structurally contained by ``root``.

    Connector registries are populated only while rendering, which is too late
    for the callout's fail-fast contract.  This small structural walk mirrors
    the element protocol rather than depending on concrete container types, so
    anchors remain discoverable through user-defined wrappers as well as the
    built-in Row/Column/Region compositions.
    """

    names: list[str] = []
    seen_elements: set[int] = set()
    seen_values: set[int] = set()

    def visit(value) -> None:
        if isinstance(value, Anchor):
            names.append(value.name)

        if isinstance(value, Element):
            ident = id(value)
            if ident in seen_elements:
                return
            seen_elements.add(ident)
            for child in getattr(value, "__dict__", {}).values():
                visit(child)
            return

        if isinstance(value, dict):
            ident = id(value)
            if ident in seen_values:
                return
            seen_values.add(ident)
            for child in value.values():
                visit(child)
            return

        if isinstance(value, (list, tuple, set, frozenset)):
            ident = id(value)
            if ident in seen_values:
                return
            seen_values.add(ident)
            for child in value:
                visit(child)

    visit(root)
    return tuple(names)


class DetailCallout(Element):
    """Place a detail beside an overview and connect it to a named anchor.

    Parameters
    ----------
    overview:
        Element containing ``Anchor(source, ...)`` at any nesting depth.
    detail:
        Expanded representation of the selected overview component.
    source:
        Name of the overview anchor being expanded.  Unknown or duplicate
        names raise at construction time instead of producing a missing line.
    target:
        Optional anchor inside ``detail`` where the expansion rails terminate.
        Placement still belongs to the complete detail subtree, which lets a
        nested hierarchy target panel (b) without enclosing its child panel
        (c) in the outer zoom funnel.
    placement:
        ``"right"`` or ``"below"`` pins a semantic reading direction.
        ``"auto"`` (default) chooses the more compact measured arrangement.
    label:
        Optional short label placed by the normal connector label placer.

    The leader is always dashed, headless, and obstacle-routed.  Nesting a
    ``DetailCallout`` in either argument naturally represents multiple detail
    levels (for example overview -> row -> processing element).
    """

    _GAP = "xl"

    def __init__(
        self,
        overview: Element,
        detail: Element,
        *,
        source: str,
        target: str | None = None,
        placement: Placement = "auto",
        label: str | None = None,
    ) -> None:
        if not isinstance(overview, Element):
            raise TypeError(
                f"overview must be an Element; got {type(overview).__name__}"
            )
        if not isinstance(detail, Element):
            raise TypeError(
                f"detail must be an Element; got {type(detail).__name__}"
            )
        if not isinstance(source, str) or not source:
            raise ValueError("source must be a non-empty anchor name")
        if placement not in ("auto", "right", "below"):
            raise ValueError(
                "placement must be 'auto', 'right', or 'below'; "
                f"got {placement!r}"
            )

        matches = [name for name in _anchor_names(overview) if name == source]
        if not matches:
            raise ValueError(
                f"DetailCallout source {source!r} is not an Anchor in overview"
            )
        if len(matches) > 1:
            raise ValueError(
                f"DetailCallout source {source!r} is ambiguous: "
                f"found {len(matches)} anchors"
            )
        if target is not None:
            if not isinstance(target, str) or not target:
                raise ValueError(
                    "target must be None or a non-empty anchor name"
                )
            target_matches = [
                name for name in _anchor_names(detail) if name == target
            ]
            if not target_matches:
                raise ValueError(
                    f"DetailCallout target {target!r} is not an Anchor in detail"
                )
            if len(target_matches) > 1:
                raise ValueError(
                    f"DetailCallout target {target!r} is ambiguous: "
                    f"found {len(target_matches)} anchors"
                )

        self.overview = overview
        self.detail = detail
        self.source = source
        self.target = target
        self.placement = placement
        self.label = label
        self._detail_anchor = f"__detail_callout_{id(self):x}"
        self._layouts: dict[str, Element] = {}

    def _auto_placement(self, theme: Theme) -> Literal["right", "below"]:
        overview = self.overview.measure(theme)
        detail = self.detail.measure(theme)
        gap = theme.gap_px(self._GAP)

        right_w = overview.w + gap + detail.w
        right_h = max(overview.h, detail.h)
        below_w = max(overview.w, detail.w)
        below_h = overview.h + gap + detail.h

        # Prefer the candidate closest to a compact square.  This makes wide
        # architecture overviews naturally expand below and tall overviews
        # naturally expand to the right, without any authored dimensions.
        def aspect_penalty(width: float, height: float) -> float:
            if width <= 0.0 or height <= 0.0:
                return float("inf")
            return abs(log(width / height))

        right_penalty = aspect_penalty(right_w, right_h)
        below_penalty = aspect_penalty(below_w, below_h)
        return "right" if right_penalty <= below_penalty else "below"

    def resolved_placement(self, theme: Theme) -> Literal["right", "below"]:
        """Return the concrete placement chosen for ``theme``."""

        if self.placement == "auto":
            return self._auto_placement(theme)
        return self.placement

    def _layout(self, theme: Theme) -> Element:
        placement = self.resolved_placement(theme)
        cached = self._layouts.get(placement)
        if cached is not None:
            return cached

        # Imports stay local so composition can export DetailCallout later
        # without creating a composition <-> connect import cycle.
        from ..connect import Connect
        from ..connect._resolver import _FlowResolver

        anchored_detail = (
            self.detail
            if self.target is not None
            else Anchor(self._detail_anchor, self.detail)
        )
        detail_target = self.target or self._detail_anchor
        if self.label is not None:
            leaders = [Connect(
                self.source,
                detail_target,
                label=self.label,
                dashed=True,
                head=False,
            )]
        elif placement == "right":
            # Two rails communicate an expanded EXTENT, not an arbitrary
            # graph edge.  Corner attachment also preserves the familiar
            # zoom-funnel silhouette without any authored coordinates.
            leaders = [
                Connect(
                    self.source, detail_target,
                    src_side="topright", dst_side="topleft",
                    dashed=True, head=False,
                    auto_route=False, style="straight",
                ),
                Connect(
                    self.source, detail_target,
                    src_side="bottomright", dst_side="bottomleft",
                    dashed=True, head=False,
                    auto_route=False, style="straight",
                ),
            ]
        else:
            leaders = [
                Connect(
                    self.source, detail_target,
                    src_side="bottomleft", dst_side="topleft",
                    dashed=True, head=False,
                    auto_route=False, style="straight",
                ),
                Connect(
                    self.source, detail_target,
                    src_side="bottomright", dst_side="topright",
                    dashed=True, head=False,
                    auto_route=False, style="straight",
                ),
            ]
        if placement == "right":
            arranged = Row(
                self.overview,
                anchored_detail,
                *leaders,
                _SourceOutline(self.source),
                gap=("md" if self.label is None else self._GAP),
                align="start",
            )
        else:
            arranged = Column(
                self.overview,
                anchored_detail,
                *leaders,
                _SourceOutline(self.source),
                gap=("md" if self.label is None else self._GAP),
                align="center",
            )

        # A local resolver makes the composition self-contained when rendered
        # directly, while Anchor's registry stack keeps it compatible with a
        # Diagram-level resolver and recursive DetailCallout compositions.
        cached = _LeaderPadding(
            _FlowResolver(arranged),
            label=self.label,
        )
        self._layouts[placement] = cached
        return cached

    def measure(self, theme: Theme) -> BBox:
        # The overview/detail gap is the leader corridor, so the resolver's
        # anchor margins and the arranged children include all leader ink in
        # the returned bbox rather than painting an out-of-band overlay.
        return self._layout(theme).measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        self._layout(theme).render(canvas, x, y, theme)


__all__ = ["DetailCallout"]
