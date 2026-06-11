"""The public :class:`Connect` element: unified API for all connectors.

See ``docs/dev/connect-api.md`` for the design note and capability map.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Union

from ..core import BBox, Canvas, Element, Theme
from ..composition import Anchor
from ._resolve import classify, synth_anchor_name, _coerce_endpoint_list, _is_element
from .inline import _InlineConnect
from .routed import _RoutedConnect
from .bus import _BusConnect


class Connect(Element):
    """Generic connector element.

    This single class subsumes the former ``Arrow``, ``Connector``, ``Flow``,
    ``Flowed``, ``Labeled``, and ``Bus``. The mode is chosen automatically
    from the shapes of ``src`` / ``dst`` — see the module docstring.
    """

    # Sentinel to detect "caller didn't pass color/label_color/style".
    _COLOR_UNSET = object()
    _STYLE_UNSET = object()

    def __init__(
        self,
        src=None,
        dst=None,
        *,
        # Labels ----------------------------------------------------------
        label: Union[str, Sequence[str], None] = None,
        label_color=_COLOR_UNSET,
        # Endpoint sides (routed mode) -----------------------------------
        src_side: str = "auto",
        dst_side: str = "auto",
        # Styling --------------------------------------------------------
        color=_COLOR_UNSET,
        dashed: bool = False,
        head: Union[bool, str] = True,
        # Routing toggle (all modes) -------------------------------------
        auto_route: bool = True,
        # Routed-mode options --------------------------------------------
        style=_STYLE_UNSET,
        curvature: float = 0.5,
        detour: float = 24.0,
        clearance: Optional[float] = None,
        # Inline-mode options --------------------------------------------
        direction: Optional[str] = None,
        length: Optional[float] = None,
        italic: bool = True,
        size: Union[str, float] = "small",
        # Bus-mode options -----------------------------------------------
        orientation: str = "auto",
    ):
        # Auto-routing is the default for every connector type. When the
        # caller does not pin ``style`` explicitly, ``auto_route`` picks
        # it: True -> topological ``"orthogonal"`` planner; False -> plain
        # ``"straight"`` line. An explicit ``style=`` always wins.
        if style is Connect._STYLE_UNSET:
            style = "orthogonal" if auto_route else "straight"
        mode = classify(src, dst, direction=direction, length=length)
        self.mode = mode

        # --- Inline mode ------------------------------------------------
        if mode == "inline":
            # Arrow's defaults: color='text_muted', label_color='muted'.
            arrow_color = "text_muted" if color is Connect._COLOR_UNSET else color
            arrow_label_color = "muted" if label_color is Connect._COLOR_UNSET else label_color
            if isinstance(label, str):
                labels = [label]
            elif label is None:
                labels = []
            else:
                labels = list(label)
            self._impl: Element = _InlineConnect(
                labels=labels,
                direction=direction,
                length=length,
                color=arrow_color,
                label_color=arrow_label_color,
                italic=italic,
                size=size,
                head=bool(head) if head is not False else False,
            )
            self._wrapped = None
            return

        # --- Routed or Bus: wrap Element endpoints in Anchors -----------
        # Flow default color is 'text'; Bus default color is 'muted_label'.
        if color is Connect._COLOR_UNSET:
            routed_color = "muted_label" if mode == "bus" else "text"
        else:
            routed_color = color
        routed_label_color = "muted" if label_color is Connect._COLOR_UNSET else label_color

        src_list = _coerce_endpoint_list(src)
        dst_list = _coerce_endpoint_list(dst)

        wrapped: List[Anchor] = []
        src_names: List[str] = []
        dst_names: List[str] = []
        for e in src_list:
            name = e if isinstance(e, str) else synth_anchor_name("src")
            if _is_element(e):
                wrapped.append(Anchor(name, e))
            src_names.append(name)
        for e in dst_list:
            name = e if isinstance(e, str) else synth_anchor_name("dst")
            if _is_element(e):
                wrapped.append(Anchor(name, e))
            dst_names.append(name)
        self._wrapped = wrapped

        if mode == "bus":
            if isinstance(label, (list, tuple)):
                # Bus accepts a single spine label; more than one would be
                # ambiguous. Join if the caller really insists.
                label_str = " ".join(label) if label else None
            else:
                label_str = label
            self._impl = _BusConnect(
                sources=src_names,
                sinks=dst_names,
                label=label_str,
                color=routed_color,
                dashed=dashed,
                head=head,
                orientation=orientation,
                auto_route=auto_route,
            )
        else:  # routed
            label_str = label if isinstance(label, str) or label is None else label[0]
            self._impl = _RoutedConnect(
                src_name=src_names[0],
                dst_name=dst_names[0],
                label=label_str,
                src_side=src_side,
                dst_side=dst_side,
                color=routed_color,
                label_color=routed_label_color,
                dashed=dashed,
                head=head,
                style=style,
                curvature=curvature,
                detour=detour,
                clearance=clearance,
            )

    # ------------------------------------------------------------------
    # Element protocol
    # ------------------------------------------------------------------

    @property
    def is_layout_invisible(self) -> bool:
        return getattr(self._impl, "is_layout_invisible", False)

    @property
    def is_inline_connector(self) -> bool:
        """Mark inline-mode connectors so :class:`Row(equal_widths=True)`
        does not inflate them into card-sized slots. Routed and bus
        connectors register as layout-invisible already, so the flag is
        only meaningful for the inline path.
        """
        return getattr(self._impl, "is_inline_connector", False)

    def measure(self, theme: Theme) -> BBox:
        return self._impl.measure(theme)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        # When auto-wrapping Elements, render the wrappers first so they
        # register anchors; Panels/Rows normally hold them, but a
        # Connect(box, label) at a fresh call site needs them too.
        if self._wrapped:
            # The wrapped anchors are held as siblings alongside the pending
            # connection spec. Because measure()/render() at this point don't
            # know the parent's layout, we render them at the caller's (x, y)
            # — which assumes the author used ``Connect.labeled`` or a
            # similar helper that controls the surrounding layout. For the
            # common routed case "Connect(anchor_name_a, anchor_name_b)" no
            # wrapping is needed and _wrapped is empty.
            for a in self._wrapped:
                a.render(canvas, x, y, theme)
        self._impl.render(canvas, x, y, theme)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @classmethod
    def labeled(cls, source: Element, label: Element, *,
                gap="md", color="text", align: str = "center") -> Element:
        """Backwards-compatible helper for the old ``Labeled(source, label)``
        pattern. Returns a composite element that renders the source, a
        short horizontal arrow, and the label, in that order.
        """
        from ..composition import Labeled as _Labeled
        return _Labeled(source, label, gap=gap, color=color, align=align)
